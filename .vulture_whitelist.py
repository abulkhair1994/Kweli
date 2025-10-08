# Vulture whitelist for false positives

# Pydantic validators require 'cls' parameter
cls  # Used in @classmethod validators

# Pydantic Config classes
Config  # Used for Pydantic configuration

# Context manager parameters
exc_type  # Used in __exit__ methods
exc_val   # Used in __exit__ methods
exc_tb    # Used in __exit__ methods
