import os

def get_data_dir():
    """Locate the data directory dynamically across different working environments."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    candidates = [
        os.path.join(parent_dir, "data"),
        os.path.join(parent_dir, "phishshift", "data"),
        os.path.join(os.getcwd(), "data"),
        os.path.join(os.getcwd(), "phishshift", "data"),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "train.csv")):
            return os.path.abspath(c)
    return os.path.abspath(os.path.join(parent_dir, "data"))
