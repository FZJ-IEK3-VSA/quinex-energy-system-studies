from rapidfuzz.distance import Levenshtein
import pandas as pd

class LevenshteinDistance:
    def __init__(self):
        pass

    def tokenize(self, text):
        return text.lower().split()

    def best_token_match(self, target_tokens, candidate_tokens, similarity = True):
        # Init set for candidate tokens that were the smallest
        matched = set()
        total_score = 0

        for target in target_tokens:
            best_score = float('inf') if not similarity else -1

            best_idx=-1
            for idx, candidate in enumerate(candidate_tokens):
                # Check if candidate token was already the smallest
                if idx in matched:
                    continue
                
                if similarity:
                    score = Levenshtein.normalized_similarity(target, candidate)
                    if score > best_score:
                        best_score = score
                        best_idx = idx

                else:
                    score = Levenshtein.distance(target, candidate)
                    if score < best_score:
                        best_score = score
                        best_idx = idx
        
            matched.add(best_idx)
            total_score += best_score

        return total_score / len(target_tokens) if target_tokens else 0

    def extended_levenshtein(self, dt, dc, similarity = True):
        tokens_dt = self.tokenize(dt)
        tokens_dc = self.tokenize(dc)

        if len(tokens_dt) > len(tokens_dc):
            return -1  # skip comparison if candidate has fewer tokens

        return self.best_token_match(tokens_dt, tokens_dc, similarity)

    def find_top_matches(self, entity_text, ontology_df, column="LABEL", top_n=20, levenshtein="similarity"):
        scores = []

        for label in ontology_df[column]:
            if pd.isna(label):
                continue    

            if levenshtein == "extended_similarity":
                score = self.extended_levenshtein(entity_text, label, True)
                reverse = True # kleinere Werte besser
            elif levenshtein == "extended_distance":
                score = self.extended_levenshtein(entity_text, label, False)
                reverse = False # kleinere Werte besser
            elif levenshtein == "distance":
                score = Levenshtein.distance(entity_text, label)
                reverse = False
            elif levenshtein == "similarity":
                score = Levenshtein.normalized_similarity(entity_text, label)
                reverse = True # höhere Werte besser
            else:
                raise ValueError(f"Unbekannte Methode: {levenshtein}")
            
            if score >= 0:
                scores.append((label, score))

        scores.sort(key=lambda x: x[1], reverse=reverse)  # kleinere Distanz = besser
        return scores[:top_n]
    
    def get_best_match(self, value, ontology_df, levenshtein="similarity", score_limit=0.8):
        if pd.isna(value) or not value.strip():
            return None, None
        
        # Top-Matches mit der Methode "extended"
        top_match = self.find_top_matches(value, ontology_df, top_n=1, levenshtein=levenshtein)
        
        if top_match:
            best_label, best_score = top_match[0]

            if (levenshtein in ["similarity", "extended_similarity"] and best_score < score_limit) or \
               (levenshtein in ["distance", "extended_distance"] and best_score > (1 - score_limit) * max(len(value), len(best_label))):  # z. B. distanz > 20 bei limit=0.8
                best_label = value
        else:
            best_label, best_score = None, None
        
        return best_label, best_score