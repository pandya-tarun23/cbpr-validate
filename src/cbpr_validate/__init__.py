"""cbpr-validate: validate ISO 20022 CBPR+ messages against the usage guidelines.

    from cbpr_validate import validate_file

    result = validate_file("payment.xml")
    result.is_compliant, result.errors, result.warnings
"""

from cbpr_validate.core import validate_bytes, validate_file, validate_string

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "validate_bytes",
    "validate_file",
    "validate_string",
]
