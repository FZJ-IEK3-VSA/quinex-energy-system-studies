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

    def find_top_matches(self, entity_text, label_list, top_n=20, levenshtein="similarity"):
        """
        Find the top matching labels from a list of strings based on a selected Levenshtein method.

        Args:
            entity_text (str): The input text to match against.
            label_list (list of str): List of label strings to compare with.
            top_n (int): Number of top matches to return.
            levenshtein (str): Method to use ("similarity", "distance", "extended_similarity", "extended_distance").
        """

        scores = []

        for label in label_list:
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
    
    def get_best_match(self, value, label_list, levenshtein="similarity"):
        """
        Get the best matching label from a list of strings.

        Args:
            value (str): The input string to match.
            label_list (list of str): List of label strings.
            levenshtein (str): The method for comparison.
        """

        if pd.isna(value) or not value.strip():
            return None, None
        
        # Top-Matches mit der Methode "extended"
        top_match = self.find_top_matches(value, label_list, top_n=1, levenshtein=levenshtein)
        
        if top_match:
            best_label, best_score = top_match[0]
        else:
            best_label, best_score = None, None
        
        return best_label, best_score