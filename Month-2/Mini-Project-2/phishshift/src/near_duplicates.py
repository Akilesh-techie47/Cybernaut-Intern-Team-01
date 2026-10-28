import re
import pandas as pd
import numpy as np


def extract_features(body_text):
    """Extract simple features from body text for rules-based baseline."""
    features = {}
    features['length'] = len(body_text)
    features['word_count'] = len(body_text.split())
    features['has_urgent'] = any(word in body_text.lower() for word in ['urgent', 'immediately', 'expired', 'suspend', 'locked', 'verify', 'confirm'])
    features['has_password'] = any(word in body_text.lower() for word in ['password', 'login', 'credential', 'sign-in'])
    features['has_financial'] = any(word in body_text.lower() for word in ['bank', 'account', 'payment', 'invoice', 'refund'])
    features['has_url'] = 'http' in body_text.lower() or 'hxxp' in body_text.lower()
    features['has_suspicious_tld'] = bool(re.search(r'[a-z]{2,3}/com|net|org|info', body_text))
    features['exclamation_count'] = body_text.count('!')
    features['question_count'] = body_text.count('?')
    return features


def remove_near_duplicates(df, body_col='body_text', hash_col='message_hash', 
                           similarity_threshold=0.85, min_group_size=2):
    """
    Remove near-duplicate message templates before creating train/valid/test partitions.
    
    Groups messages by similarity and ensures duplicate groups don't leak across partitions.
    Returns a DataFrame with duplicate groups identified and removed from the main partitions.
    """
    df = df.copy()
    
    # Compute character-level hash for grouping
    df['body_hash'] = df[body_col].apply(lambda x: hash(x[:200]))
    
    # Group by prefix similarity (same subject prefix + similar body)
    df['subject_prefix'] = df['subject_or_title'].apply(
        lambda x: x.split(':')[0] if ':' in x else x.split()[0] if x.split() else ''
    )
    
    # Simple similarity: Jaccard on word sets
    def jaccard_similarity(a, b):
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
    
    # Compute pairwise similarities within subject prefix groups
    duplicates_removed = []
    duplicate_groups = []
    
    subject_groups = df.groupby('subject_prefix')
    
    for prefix, group_df in subject_groups:
        if len(group_df) <= 1:
            # No potential duplicates in this group
            duplicates_removed.append(group_df)
            continue
        
        # Compute pairwise similarities
        kept_indices = [group_df.index[0]]
        removed_indices = []
        
        for idx in group_df.index[1:]:
            current_row = df.loc[idx]
            is_duplicate = False
            
            for kept_idx in kept_indices:
                similarity = jaccard_similarity(
                    df.loc[kept_idx][body_col],
                    current_row[body_col]
                )
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break
            
            if is_duplicate:
                removed_indices.append(idx)
            else:
                kept_indices.append(idx)
        
        # Separate kept and removed
        kept = df.loc[kept_indices]
        removed = df.loc[removed_indices]
        
        duplicates_removed.append(kept)
        if len(removed) > 0:
            duplicate_groups.append(removed)
    
    result_kept = pd.concat([d for d in duplicates_removed if len(d) > 0])
    result_kept = result_kept.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Collect all duplicate groups
    all_duplicate_frames = []
    for dg in duplicate_groups:
        all_duplicate_frames.append(dg)
    all_duplicates = pd.concat(all_duplicate_frames, ignore_index=True) if all_duplicate_frames else pd.DataFrame()
    
    # Record removal statistics
    total_removed = len(df) - len(result_kept)
    print(f"Near-duplicate removal: {total_removed} duplicates removed out of {len(df)} messages")
    print(f"Kept: {len(result_kept)} messages, Duplicates in {len(duplicate_groups)} groups")
    
    return result_kept, all_duplicates


def split_by_campaign(df, campaign_col='campaign_group', 
                      train_campaigns=None, valid_campaigns=None, test_campaigns=None,
                      random_state=42):
    """
    Split data into train/valid/test partitions ensuring no campaign group leakage.
    If campaign lists not provided, use stratified split by campaign group distribution.
    """
    np.random.seed(random_state)
    
    unique_campaigns = df[campaign_col].unique()
    
    if train_campaigns is None:
        # Default: 70/15/15 split of campaigns
        np.random.shuffle(unique_campaigns)
        n_train = int(0.7 * len(unique_campaigns))
        n_valid = int(0.15 * len(unique_campaigns))
        train_campaigns = set(unique_campaigns[:n_train])
        valid_campaigns = set(unique_campaigns[n_train:n_train+n_valid])
        test_campaigns = set(unique_campaigns[n_train+n_valid:])
    
    else:
        train_campaigns = set(train_campaigns)
        valid_campaigns = set(valid_campaigns) if valid_campaigns else set()
        test_campaigns = set(test_campaigns) if test_campaigns else set()
        # Ensure no overlap
        assert len(train_campaigns & valid_campaigns) == 0
        assert len(train_campaigns & test_campaigns) == 0
        assert len(valid_campaigns & test_campaigns) == 0
    
    train_df = df[df[campaign_col].isin(train_campaigns)].copy()
    valid_df = df[df[campaign_col].isin(valid_campaigns)].copy()
    test_df = df[df[campaign_col].isin(test_campaigns)].copy()
    
    print(f"Campaign split: train={len(train_campaigns)} campaigns, "
          f"valid={len(valid_campaigns)} campaigns, test={len(test_campaigns)} campaigns")
    print(f"  -> train: {len(train_df)} rows, valid: {len(valid_df)} rows, test: {len(test_df)} rows")
    
    return train_df, valid_df, test_df


if __name__ == "__main__":
    try:
        from src.utils import get_data_dir
    except ImportError:
        from utils import get_data_dir
    data_dir = get_data_dir()
    
    # Load dataset
    df = pd.read_csv(os.path.join(data_dir, "raw_messages.csv"))
    print(f"Loaded dataset: {len(df)} rows")
    
    # Remove near-duplicates
    kept, duplicates = remove_near_duplicates(df, similarity_threshold=0.85)
    print(f"\nAfter near-duplicate removal: {len(kept)} messages kept")
    
    # Split by campaign
    train, valid, test = split_by_campaign(kept, random_state=42)
    
    # Save partitions
    train.to_csv(os.path.join(data_dir, "train.csv"), index=False)
    valid.to_csv(os.path.join(data_dir, "valid.csv"), index=False)
    test.to_csv(os.path.join(data_dir, "test.csv"), index=False)
    duplicates.to_csv(os.path.join(data_dir, "duplicate_groups.csv"), index=False)
    
    print("\nPartitions saved to:")
    print(f"  {data_dir}")