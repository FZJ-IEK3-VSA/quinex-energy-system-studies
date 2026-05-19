import logging
import os
import re
import json
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OpenAlexError(Exception):
    """Base exception for OpenAlex client errors."""


class OpenAlexRequestError(OpenAlexError):
    """Raised when an OpenAlex API request fails."""


class OpenAlexClient:
    """Client for retrieving and processing publication data from the OpenAlex API."""

    DOI_PATTERN = re.compile(r"^10\.[^/\s]+/\S+$", re.IGNORECASE)

    def __init__(self, base_url: str = "https://api.openalex.org", timeout: int = 30):
        """Initialize the OpenAlex client.

        Args:
            base_url (str): Base URL for the OpenAlex API.
            timeout (int): Timeout for HTTP requests in seconds.
        """
        load_dotenv()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = os.getenv("OPENALEX_API_KEY")
        self.mailto = os.getenv("OPENALEX_MAILTO")
        self.session = requests.Session()
        self._configure_session_retries()
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_by_doi(
        self, doi: str | list[str]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Fetch OpenAlex work record(s) by DOI.

        Args:
            doi (str | list[str]): Single DOI or list of DOIs to query.

        Returns:
            dict[str, Any] | list[dict[str, Any]]:
                Single work response for a string DOI, or a list of work responses
                for DOI lists.

        Raises:
            ValueError: If DOI input is missing or malformed.
            OpenAlexRequestError: If request fails or response is invalid.
        """
        if isinstance(doi, str):
            return self._fetch_single_by_doi(doi)

        if not isinstance(doi, list) or not doi:
            raise ValueError("doi must be a non-empty string or a non-empty list of strings.")

        normalized_dois = [self._normalize_and_validate_doi(item) for item in doi]
        return self._fetch_multiple_by_doi(normalized_dois)

    def extract_funding_and_institutions(
        self,
        api_response: dict[str, Any] | list[dict[str, Any]],
        output_path: str | None = None,
    ) -> (
        dict[str, list[dict[str, Any]] | list[str]]
        | list[dict[str, list[dict[str, Any]] | list[str]]]
    ):
        """Extract funders, institutions, and topic metadata from OpenAlex work response(s).

        Args:
            api_response (dict[str, Any] | list[dict[str, Any]]):
                Full OpenAlex work response or list of work responses.
            output_path (str | None):
                Optional path to write a JSON file that maps DOI to extracted
                funders and institutions.

        Returns:
            dict[str, list[dict[str, Any]] | list[str]] | list[dict[str, list[dict[str, Any]] | list[str]]]:
                For a single response, returns one dictionary with keys
                'funders', 'institutions', 'field', 'subfield', 'domain',
                'concepts', 'topics', and 'author_origins'. For a list input,
                returns a list of such dictionaries.

        Raises:
            ValueError: If api_response is not a dictionary or list of dictionaries.
        """
        doi_to_extracted: dict[str, dict[str, list[dict[str, Any]] | list[str]]] = {}

        if isinstance(api_response, list):
            extracted_list: list[dict[str, list[dict[str, Any]] | list[str]]] = []
            for item in api_response:
                if not isinstance(item, dict):
                    raise ValueError(
                        "api_response list must contain only dictionaries."
                    )
                extracted = self._extract_funding_and_institutions_single(item)
                extracted_list.append(extracted)
                self._add_extracted_result_by_doi(item, extracted, doi_to_extracted)

            if output_path:
                self._write_results_by_doi(output_path, doi_to_extracted)

            return extracted_list

        if not isinstance(api_response, dict):
            raise ValueError("api_response must be a dictionary or a list of dictionaries.")

        extracted_single = self._extract_funding_and_institutions_single(api_response)
        self._add_extracted_result_by_doi(api_response, extracted_single, doi_to_extracted)

        if output_path:
            self._write_results_by_doi(output_path, doi_to_extracted)

        return extracted_single

    def _add_extracted_result_by_doi(
        self,
        api_response: dict[str, Any],
        extracted: dict[str, list[dict[str, Any]] | list[str]],
        doi_to_extracted: dict[str, dict[str, list[dict[str, Any]] | list[str]]],
    ) -> None:
        """Add extracted result to DOI keyed dictionary if DOI is present and valid."""
        raw_doi = api_response.get("doi")
        if not isinstance(raw_doi, str) or not raw_doi.strip():
            self.logger.warning("Skipping result without DOI when building output mapping.")
            return

        try:
            normalized_doi = self._normalize_and_validate_doi(raw_doi)
        except ValueError:
            self.logger.warning(
                "Skipping result with invalid DOI '%s' when building output mapping.",
                raw_doi,
            )
            return

        doi_to_extracted[normalized_doi] = extracted

    def _write_results_by_doi(
        self,
        output_path: str,
        doi_to_extracted: dict[str, dict[str, list[dict[str, Any]] | list[str]]],
    ) -> None:
        """Append DOI keyed extracted results to JSON, overwriting duplicate DOI keys."""
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        existing_data: dict[str, dict[str, list[dict[str, Any]] | list[str]]] = {}
        if os.path.exists(output_path):
            try:
                with open(output_path, encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    existing_data = loaded
                else:
                    self.logger.warning(
                        "Existing output file %s does not contain a JSON object. "
                        "Starting with an empty mapping.",
                        output_path,
                    )
            except (OSError, json.JSONDecodeError) as exc:
                self.logger.warning(
                    "Could not read existing output file %s (%s). "
                    "Starting with an empty mapping.",
                    output_path,
                    exc,
                )

        existing_data.update(doi_to_extracted)

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=2)

        self.logger.info(
            "Saved %d DOI mapped funding/institutions result(s) to %s (total DOI entries: %d)",
            len(doi_to_extracted),
            output_path,
            len(existing_data),
        )

    def _fetch_single_by_doi(self, doi: str) -> dict[str, Any]:
        """Fetch a single OpenAlex work record by DOI."""
        normalized_doi = self._normalize_and_validate_doi(doi)
        encoded_doi = quote(normalized_doi, safe="")
        url = f"{self.base_url}/works/doi:{encoded_doi}"

        self.logger.info("Fetching OpenAlex work for DOI %s", normalized_doi)

        params = self._build_common_params()

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise OpenAlexRequestError(
                    f"No OpenAlex work found for DOI '{normalized_doi}'."
                ) from exc
            raise OpenAlexRequestError(
                f"OpenAlex request failed for DOI '{normalized_doi}': {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise OpenAlexRequestError(
                f"Could not reach OpenAlex API for DOI '{normalized_doi}': {exc}"
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise OpenAlexRequestError(
                f"OpenAlex returned invalid JSON for DOI '{normalized_doi}'."
            ) from exc

    def _fetch_multiple_by_doi(self, normalized_dois: list[str]) -> list[dict[str, Any]]:
        """Fetch multiple OpenAlex works by DOI in a single API call."""
        if not normalized_dois:
            return []

        self.logger.info("Fetching %d OpenAlex works in one request", len(normalized_dois))

        filter_value = f"doi:{'|'.join(normalized_dois)}"
        if len(filter_value) > 6000:
            raise OpenAlexRequestError(
                "Batch DOI filter is too large for a single OpenAlex request. "
                "Reduce DOI count per call (for example, chunk into smaller batches)."
            )

        params = self._build_common_params(
            {
                "filter": filter_value,
                "per-page": len(normalized_dois),
            }
        )

        try:
            response = self.session.get(
                f"{self.base_url}/works", params=params, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise OpenAlexRequestError(
                f"OpenAlex batch request failed for {len(normalized_dois)} DOIs: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise OpenAlexRequestError(
                f"Could not reach OpenAlex API for batch DOI request: {exc}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenAlexRequestError(
                "OpenAlex returned invalid JSON for batch DOI request."
            ) from exc

        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            raise OpenAlexRequestError(
                "OpenAlex batch response has invalid format: 'results' is not a list."
            )

        works_by_doi: dict[str, dict[str, Any]] = {}
        for work in results:
            if not isinstance(work, dict):
                continue

            raw_doi = work.get("doi")
            if not isinstance(raw_doi, str) or not raw_doi.strip():
                continue

            try:
                normalized_result_doi = self._normalize_and_validate_doi(raw_doi)
            except ValueError:
                continue

            works_by_doi[normalized_result_doi] = work

        ordered_works = [works_by_doi[doi] for doi in normalized_dois if doi in works_by_doi]

        missing_dois = [doi for doi in normalized_dois if doi not in works_by_doi]
        if missing_dois:
            self.logger.warning(
                "OpenAlex did not return records for %d DOI(s): %s",
                len(missing_dois),
                ", ".join(missing_dois),
            )

        return ordered_works

    def _build_common_params(self, extra_params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build query parameters shared across OpenAlex requests."""
        params: dict[str, Any] = {}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto
        if extra_params:
            params.update(extra_params)
        return params

    def _configure_session_retries(self) -> None:
        """Configure retries for transient HTTP/network failures."""
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _extract_funding_and_institutions_single(
        self, api_response: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]] | list[str]]:
        """Extract funding, institution, and topic metadata from one OpenAlex work response."""

        funders = self._extract_funders(api_response)
        institutions = self._extract_institutions(api_response)
        field, subfield, domain = self._extract_field_subfield_domain(api_response)
        concepts = self._extract_concepts(api_response)
        topics = self._extract_topics(api_response)
        author_origins = self._extract_author_origins(api_response)

        return {
            "funders": funders,
            "institutions": institutions,
            "field": field,
            "subfield": subfield,
            "domain": domain,
            "concepts": concepts,
            "topics": topics,
            "author_origins": author_origins,
        }

    def _extract_author_origins(self, api_response: dict[str, Any]) -> list[str]:
        """Extract unique author country codes from OpenAlex authorships."""
        authorships = api_response.get("authorships", [])
        if not isinstance(authorships, list):
            return []

        origins: list[str] = []
        seen_origins: set[str] = set()

        def add_origin(value: Any) -> None:
            if not isinstance(value, str):
                return

            normalized = value.strip().upper()
            if not normalized or normalized in seen_origins:
                return

            seen_origins.add(normalized)
            origins.append(normalized)

        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue

            countries = authorship.get("countries", [])
            if isinstance(countries, list):
                for country in countries:
                    add_origin(country)

            institutions = authorship.get("institutions", [])
            if isinstance(institutions, list):
                for institution in institutions:
                    if isinstance(institution, dict):
                        add_origin(institution.get("country_code"))

        return origins

    def _extract_field_subfield_domain(
        self, api_response: dict[str, Any]
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract unique field/subfield/domain names from primary_topic and topics."""
        fields: list[str] = []
        subfields: list[str] = []
        domains: list[str] = []
        seen_fields: set[str] = set()
        seen_subfields: set[str] = set()
        seen_domains: set[str] = set()

        def add_topic_entities(topic: dict[str, Any]) -> None:
            subfield = topic.get("subfield")
            field = topic.get("field")
            domain = topic.get("domain")

            if isinstance(subfield, dict):
                display_name = subfield.get("display_name")
                if isinstance(display_name, str):
                    normalized = display_name.strip()
                    if normalized and normalized not in seen_subfields:
                        seen_subfields.add(normalized)
                        subfields.append(normalized)

            if isinstance(field, dict):
                display_name = field.get("display_name")
                if isinstance(display_name, str):
                    normalized = display_name.strip()
                    if normalized and normalized not in seen_fields:
                        seen_fields.add(normalized)
                        fields.append(normalized)

            if isinstance(domain, dict):
                display_name = domain.get("display_name")
                if isinstance(display_name, str):
                    normalized = display_name.strip()
                    if normalized and normalized not in seen_domains:
                        seen_domains.add(normalized)
                        domains.append(normalized)

        primary_topic = api_response.get("primary_topic")
        if isinstance(primary_topic, dict):
            add_topic_entities(primary_topic)

        topics = api_response.get("topics", [])
        if isinstance(topics, list):
            for topic in topics:
                if isinstance(topic, dict):
                    add_topic_entities(topic)

        return fields, subfields, domains

    def _extract_concepts(self, api_response: dict[str, Any]) -> list[str]:
        """Extract unique concept names."""
        concepts = api_response.get("concepts", [])
        if not isinstance(concepts, list):
            return []

        concept_names: list[str] = []
        seen_concepts: set[str] = set()

        for concept in concepts:
            if not isinstance(concept, dict):
                continue

            display_name = concept.get("display_name")
            if not isinstance(display_name, str):
                continue

            normalized = display_name.strip()
            if not normalized or normalized in seen_concepts:
                continue

            seen_concepts.add(normalized)
            concept_names.append(normalized)

        return concept_names

    def _extract_topics(self, api_response: dict[str, Any]) -> list[str]:
        """Extract unique topic names from primary_topic and topics."""
        topic_names: list[str] = []
        seen_topics: set[str] = set()

        def add_topic_name(topic: dict[str, Any]) -> None:
            display_name = topic.get("display_name")
            if not isinstance(display_name, str):
                return

            normalized = display_name.strip()
            if not normalized or normalized in seen_topics:
                return

            seen_topics.add(normalized)
            topic_names.append(normalized)

        primary_topic = api_response.get("primary_topic")
        if isinstance(primary_topic, dict):
            add_topic_name(primary_topic)

        topics = api_response.get("topics", [])
        if isinstance(topics, list):
            for topic in topics:
                if isinstance(topic, dict):
                    add_topic_name(topic)

        return topic_names

    def _normalize_and_validate_doi(self, doi: str) -> str:
        """Normalize DOI inputs and validate basic DOI format."""
        if not isinstance(doi, str) or not doi.strip():
            raise ValueError("DOI must be a non-empty string.")

        cleaned = doi.strip()
        cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.lower()

        if not self.DOI_PATTERN.match(cleaned):
            raise ValueError(f"Invalid DOI format: '{doi}'.")

        return cleaned

    def _extract_funders(self, api_response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract and de-duplicate funder information from OpenAlex grants."""
        grants = api_response.get("grants", [])
        if not isinstance(grants, list):
            return []

        funders_by_key: dict[str, dict[str, Any]] = {}

        for grant in grants:
            if not isinstance(grant, dict):
                continue

            funder_id = grant.get("funder")
            funder_name = grant.get("funder_display_name")

            if not funder_id and not funder_name:
                continue

            key = str(funder_id or funder_name)
            if key not in funders_by_key:
                funders_by_key[key] = {
                    "id": funder_id,
                    "display_name": funder_name,
                }

        return list(funders_by_key.values())

    def _extract_institutions(self, api_response: dict[str, Any]) -> list[str]:
        """Extract unique institution types from OpenAlex authorships."""
        authorships = api_response.get("authorships", [])
        if not isinstance(authorships, list):
            return []

        institution_types: list[str] = []
        seen_types: set[str] = set()

        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue

            institutions = authorship.get("institutions", [])
            if not isinstance(institutions, list):
                continue

            for institution in institutions:
                if not isinstance(institution, dict):
                    continue

                institution_type = institution.get("type")
                if not isinstance(institution_type, str) or not institution_type.strip():
                    continue

                normalized_type = institution_type.strip()
                if normalized_type in seen_types:
                    continue

                seen_types.add(normalized_type)
                institution_types.append(normalized_type)

        return institution_types