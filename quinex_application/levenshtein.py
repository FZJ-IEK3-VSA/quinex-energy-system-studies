from rapidfuzz.distance import Levenshtein
import pandas as pd

class LevenshteinDistance:
    #     def __init__():

    def tokenize(self, text):
        return text.lower().split()

    def best_token_match(self, target_tokens, candidate_tokens):
        # Init set for candidate tokens that were the smallest
        matched = set()
        total_score = 0

        for target in target_tokens:
            min_dist = float('inf')

            best_idx=-1
            for idx, candidate in enumerate(candidate_tokens):
                # Check if candidate token was already the smallest
                if idx in matched:
                    continue
                
                # Distance between target token and candidate token
                dist = Levenshtein.distance(target, candidate)

                # Check if the distance is smallest
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx
        
            matched.add(best_idx)
            total_score += min_dist

        return total_score / len(target_tokens)

    def extended_levenshtein(self, dt, dc):
        tokens_dt = self.tokenize(dt)
        tokens_dc = self.tokenize(dc)

        if len(tokens_dt) > len(tokens_dc):
            return -1  # skip comparison if candidate has fewer tokens

        return self.best_token_match(tokens_dt, tokens_dc)

    def find_top_matches(self, entity_text, ontology_df, column="LABEL", top_n=20, levensthein="extended"):
        scores = []

        for label in ontology_df[column]:
            if pd.isna(label):
                continue    

            if levensthein == "extended":
                score = self.extended_levenshtein(entity_text, label)
                reverse = False # kleinere Werte besser
            elif levensthein == "distance":
                score = Levenshtein.distance(entity_text, label)
                reverse = False
            elif levensthein == "similarity":
                score = Levenshtein.normalized_similarity(entity_text, label)
                reverse = True # höhere Werte besser
            else:
                raise ValueError(f"Unbekannte Methode: {levensthein}")
            
            if score >= 0:
                scores.append((label, score))

        scores.sort(key=lambda x: x[1], reverse=reverse)  # kleinere Distanz = besser
        return scores[:top_n]