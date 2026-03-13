import re
import time
import json
import pandas as pd
from tqdm import tqdm
from geopy import distance
from quinex_application.postprocessing.language_model import LanguageModel


class SpatialNormalization:
    """
    Normalizes spatial scope descriptions in analysis results using LLM-based geocoding.
    """
    
    def __init__(self):
        """
        Initialize the SpatialNormalization instance.
        """

        self.llm = LanguageModel()
    
    def get_geo_information_from_spatial_scope(
            self, 
            df_filtered,
            nbr_runs_per_model=2,
            predicted_geo_coordinates_cache_path="cached_predicted_geo_coordinates.json",
            rerun_those_that_failed_earlier=True,
            update_spatial_scopes=True,
            dist_deviation_threshold_in_km=300,
            models=None
            ):
        """
        Get geo information for natural language location descriptions using the Blablador API.
        
        Args:
            df_filtered: Filtered dataframe with spatial scope information
            nbr_runs_per_model: Number of runs per model
            predicted_geo_coordinates_cache_path: Path to cache file
            rerun_those_that_failed_earlier: Whether to rerun failed predictions
            update_spatial_scopes: Whether to update spatial scopes
            dist_deviation_threshold_in_km: Deviation threshold in km
            models: List of model names to use. If None, automatically selects top 2 models.
        
        Returns:
            A triple of (country, latitude, longitude) if successful, or None if geocoding fails.
        """

        def is_valid_coordinate(lat, lon):
            """Centralized coordinate validation."""
            if lat is None or lon is None:
                return False
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return False
            if lat == 0 and lon == 0:
                return False
            return True

        def get_spatial_scope_text(x):
            if isinstance(x, dict):
                return x.get("text", "")
            return str(x) if x else ""
        
        # -------------------- LOAD CACHE --------------------
        try:
            with open(predicted_geo_coordinates_cache_path, "r") as f:
                predicted_geo_coordinates = json.load(f)
        except FileNotFoundError:
            print("No cached predicted coordinates found. Starting geolocation from scratch.")
            predicted_geo_coordinates = {}
        
        # Use provided models or select top 2 automatically
        if models is None:
            models = self.llm.select_model(2)
        print(models)

        # Get available models from API
        try:
            available_models = self.llm.get_models()
        except Exception as e:
            print(f"Warning: Could not fetch available models: {e}. Using only cache data.")
            available_models = []

        all_spatial_scopes = (
            df_filtered["spatial_scope"]
            .apply(get_spatial_scope_text)
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )


        # -------------------- LLM GEOLOCATION --------------------
        for model in models:
            if model not in predicted_geo_coordinates:
                    predicted_geo_coordinates[model] = {}

            not_yet_geolocated_spatial_scopes = []
            for scope in all_spatial_scopes:
                if scope not in predicted_geo_coordinates[model] \
                    or len(predicted_geo_coordinates[model][scope]) < nbr_runs_per_model \
                        or (rerun_those_that_failed_earlier and any(None in pred.values() for pred in predicted_geo_coordinates[model][scope])):
                    not_yet_geolocated_spatial_scopes.append(scope)

            # Check if model is available before attempting LLM calls
            model_is_available = model in available_models
            
            if not model_is_available:
                print(f"Model '{model}' is not available. Skipping LLM calls. Using only cache data for this model.")
            
            if update_spatial_scopes and len(not_yet_geolocated_spatial_scopes) > 0 and model_is_available:
                # Geolocate missing spatial scopes.
                print(f"\n>>>>>>>>>>>>>>> Geolocating missing {len(not_yet_geolocated_spatial_scopes)} of {len(all_spatial_scopes)} unique spatial scopes")
                
                prompt_template = 'Return the country, latitude and longitude that best matches the following place description and only answer with a JSON response without any comments in the format {{"country": 0, "latitude": 0, "longitude": 0}}.\nPlace description: "{location_str}"\nJSON: {{"'
                
                for location_str in tqdm(not_yet_geolocated_spatial_scopes, desc="Geolocating spatial scopes"):
                    
                    prompt = prompt_template.format(location_str=location_str)

                    trials = 0
                    max_trials = 5
                    while trials < max_trials:
                        response = self.llm.chat(prompt, model=model, verbose=False)
                        if response is None:
                            print(f"LLM returned None for '{location_str}'. Waiting 10 minutes before retrying...")
                            time.sleep(600)
                            trials += 1
                            continue
                        if response.startswith('{"error":') or response.startswith('<!DOCTYPE HTML PUBLIC'):
                            trials += 1
                            time.sleep(1)
                        else:
                            break
                    
                    pred_geo_coords = []
                    try:      
                        json_answer = self.extract_json_from_response(response)

                        lat = json_answer["latitude"]
                        lon = json_answer["longitude"]

                        if is_valid_coordinate(lat, lon):
                            pred_geo_coord = {
                                "text": location_str,
                                "country": json_answer.get("country"),
                                "latitude": lat,
                                "longitude": lon,
                            }
                            pred_geo_coords.append(pred_geo_coord)
                        #else:
                            #print(f"Invalid coordinates ({lat}, {lon}) for location '{location_str}'")
                
                    except Exception as e:
                        # If API response is not a valid JSON, print error and continue.
                        print(f"Error processing response '{response}' for location '{location_str}': {e}")
                        continue

                    predicted_geo_coordinates[model][location_str] = pred_geo_coords
                
                # Save predicted coordinates to file.    
                with open(predicted_geo_coordinates_cache_path, "w") as f:
                    json.dump(predicted_geo_coordinates, f, indent=4, ensure_ascii=False)
        

        # -------------------- COLLECT VALID COORDS --------------------
        dist_sum_per_location = {}

        for model_id in predicted_geo_coordinates.keys():
            for location_str, coord_preds in predicted_geo_coordinates[model_id].items():
                for coords in coord_preds:
                    lat = coords.get("latitude")
                    lon = coords.get("longitude")
                    if is_valid_coordinate(lat, lon):
                        if location_str not in dist_sum_per_location:
                            dist_sum_per_location[location_str] = []
                        dist_sum_per_location[location_str].append((lat, lon))
    

        # -------------------- AVERAGE + DEVIATION --------------------
        averaged_coords = {}

        for location_str, coords_list in dist_sum_per_location.items():
            # Calculate average coordinates.
            avg_lat = sum(coord[0] for coord in coords_list) / len(coords_list)
            avg_lon = sum(coord[1] for coord in coords_list) / len(coords_list)
            average_coords = (avg_lat, avg_lon)

            if len(coords_list) > 1:
                distances_in_km = []
                for coord in coords_list:
                    # Calculate distance to average coordinates.
                    distances_in_km.append(distance.distance(coord, average_coords).km)

                distances_in_km_mean = sum(distances_in_km) / len(distances_in_km)

                if distances_in_km_mean > dist_deviation_threshold_in_km:
                    coords_str = ", ".join(
                        f"({coord[0]:.6f}, {coord[1]:.6f})"
                        for coord in coords_list
                    )
                    print(
                        f"High deviation ({distances_in_km_mean:.2f} km) "
                        f"for '{location_str}' → ignored. "
                        f"Coordinates: {coords_str}"
                    )
                    continue
                
                averaged_coords[location_str] = {"latitude": avg_lat, "longitude": avg_lon}


        # -------------------- BUILD REFINED COLUMN --------------------
        def build_refined(row):
            text = get_spatial_scope_text(row["spatial_scope"])
            if text not in averaged_coords:
                return pd.NA

            country = None
            for model_preds in predicted_geo_coordinates.values():
                preds = model_preds.get(text, [])
                for pred in preds:
                    if pred.get("country"):
                        country = pred["country"]
                        break
                if country:
                    break

            return {
                "text": text,
                "country": country,
                "latitude": averaged_coords[text]["latitude"],
                "longitude": averaged_coords[text]["longitude"],
            }

        df_filtered["spatial_scope_refined"] = df_filtered.apply(build_refined, axis=1)
        return df_filtered


    def extract_json_from_response(self, response: str):
        """
        Extract the first JSON object from a string.
        Returns dict or raises ValueError.
        """
        match = re.search(r'\{[\s\S]*?\}', response)
        if not match:
            raise ValueError("No JSON object found in response")

        json_str = match.group(0)
        return json.loads(json_str)

