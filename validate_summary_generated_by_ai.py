import json
import yaml
import re
import os
from typing import Dict, List, Any, Tuple


def validate_video_summary(json_data: str, yaml_rules_path: str) -> Dict:
    """
    Validate video summary metadata JSON against YAML rules loaded from a file
    """
    # Parse JSON data
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError:
        return {
            "valid": False,
            "error": "Invalid JSON format",
            "segments_validation": [],
            "summary": {
                "total_segments": 0,
                "valid_segments": 0,
                "invalid_segments": 0,
                "overall_status": "FAIL",
            },
        }

    # Load YAML rules from file
    try:
        if not os.path.exists(yaml_rules_path):
            return {
                "valid": False,
                "error": f"YAML rules file not found: {yaml_rules_path}",
                "segments_validation": [],
                "summary": {
                    "total_segments": 0,
                    "valid_segments": 0,
                    "invalid_segments": 0,
                    "overall_status": "FAIL",
                },
            }

        with open(yaml_rules_path, "r") as file:
            yaml_content = file.read()
            rules = yaml.safe_load(yaml_content)
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error loading YAML rules: {str(e)}",
            "segments_validation": [],
            "summary": {
                "total_segments": 0,
                "valid_segments": 0,
                "invalid_segments": 0,
                "overall_status": "FAIL",
            },
        }

    # Helper functions for validation
    def validate_field_structure(
        field_value: Any, field_rules: Dict, field_name: str
    ) -> Tuple[bool, List[str]]:
        """Validate a field against its structure rules"""
        errors = []

        # Check if field is required but missing
        if field_rules.get("required", False) and field_value is None:
            errors.append(f"Required field '{field_name}' is missing")
            return False, errors

        # If field is not required and is None, skip further validation
        if not field_rules.get("required", False) and field_value is None:
            return True, errors

        # Validate field type
        field_type = field_rules.get("type")
        if field_type == "string" and not isinstance(field_value, str):
            errors.append(f"Field '{field_name}' should be a string")
        elif field_type == "number" and not isinstance(field_value, (int, float)):
            errors.append(f"Field '{field_name}' should be a number")
        elif field_type == "array" and not isinstance(field_value, list):
            errors.append(f"Field '{field_name}' should be an array")
        elif field_type == "object" and not isinstance(field_value, dict):
            errors.append(f"Field '{field_name}' should be an object")

        # Validate string fields
        if field_type == "string" and isinstance(field_value, str):
            # Validate min_length
            min_length = field_rules.get("min_length")
            if min_length is not None and len(field_value) < min_length:
                errors.append(
                    f"Field '{field_name}' length should be at least {min_length}"
                )

            # Validate pattern
            pattern = field_rules.get("pattern")
            if pattern is not None and not re.match(pattern, field_value):
                errors.append(f"Field '{field_name}' does not match required pattern")

            # Validate enum
            enum_values = field_rules.get("enum")
            if enum_values is not None and field_value not in enum_values:
                errors.append(f"Field '{field_name}' should be one of {enum_values}")

        # Validate array fields
        if field_type == "array" and isinstance(field_value, list):
            # Validate min_items
            min_items = field_rules.get("min_items")
            if min_items is not None and len(field_value) < min_items:
                errors.append(
                    f"Field '{field_name}' should have at least {min_items} items"
                )

        # Validate number fields
        if field_type == "number" and isinstance(field_value, (int, float)):
            # Validate min
            min_val = field_rules.get("min")
            if min_val is not None and field_value < min_val:
                errors.append(f"Field '{field_name}' should be at least {min_val}")

            # Validate max
            max_val = field_rules.get("max")
            if max_val is not None and field_value > max_val:
                errors.append(f"Field '{field_name}' should be at most {max_val}")

            # Validate threshold
            threshold = field_rules.get("threshold")
            if threshold is not None and field_value < threshold:
                errors.append(f"Field '{field_name}' should be at least {threshold}")

        # Validate confidence threshold
        if field_name.endswith("confidence"):
            threshold = field_rules.get("threshold")
            if threshold is not None:
                # Convert confidence levels to numeric values for comparison
                confidence_levels = {"low": 1, "medium": 2, "high": 3}
                required_level = confidence_levels.get(threshold, 0)
                actual_level = confidence_levels.get(field_value, 0)

                if actual_level < required_level:
                    errors.append(
                        f"Field '{field_name}' should be at least '{threshold}'"
                    )

        return len(errors) == 0, errors

    # Validate segments field
    segments_rules = rules["validation"]["structure"]["fields"]["segments"]

    if "segments" not in data:
        return {
            "valid": False,
            "error": "Required field 'segments' is missing",
            "segments_validation": [],
            "summary": {
                "total_segments": 0,
                "valid_segments": 0,
                "invalid_segments": 0,
                "overall_status": "FAIL",
            },
        }

    if not isinstance(data["segments"], list):
        return {
            "valid": False,
            "error": "Field 'segments' should be an array",
            "segments_validation": [],
            "summary": {
                "total_segments": 0,
                "valid_segments": 0,
                "invalid_segments": 0,
                "overall_status": "FAIL",
            },
        }

    # Check min_items constraint for segments
    min_segments = segments_rules.get("min_items", 0)
    if len(data["segments"]) < min_segments:
        return {
            "valid": False,
            "error": f"There should be at least {min_segments} segments",
            "segments_validation": [],
            "summary": {
                "total_segments": len(data["segments"]),
                "valid_segments": 0,
                "invalid_segments": len(data["segments"]),
                "overall_status": "FAIL",
            },
        }

    # Validate each segment
    segments_validation = []
    valid_segments = 0

    for i, segment in enumerate(data["segments"]):
        segment_validation = {
            "segment_index": i,
            "segment_title": segment.get(
                "Segment Title", segment.get("segment_title", "Unknown")
            ),
            "valid": True,
            "field_validations": {},
        }

        # Get item schema for segment
        item_schema = segments_rules["item_schema"]
        field_rules = item_schema["fields"]

        # Define mapping between YAML field names and possible JSON field names
        field_name_mapping = {
            "segment_title": ["Segment Title", "segment_title"],
            "timestamps": ["Timestamps", "timestamps"],
            "editorial_subjects": ["Editorial subjects", "editorial_subjects"],
            "visual_subjects": ["Visual Subjects", "visual_subjects"],
            "names": ["Names", "names"],
            "location": ["Location", "location"],
        }

        # Validate each field in the segment
        for field_name, possible_json_names in field_name_mapping.items():
            # Find the field in JSON
            field_value = None
            json_field_name = None
            for json_name in possible_json_names:
                if json_name in segment:
                    field_value = segment[json_name]
                    json_field_name = json_name
                    break

            # Get validation rules for this field
            field_rule = field_rules.get(field_name, {})

            # Validate field structure
            valid, errors = validate_field_structure(
                field_value, field_rule, field_name
            )

            # Check for confidence and score
            confidence_value = segment.get("confidence")
            score_value = segment.get("score")

            # If segment-level confidence/score is present, use them for validation
            if confidence_value is not None and "confidence" in field_rule:
                confidence_rule = field_rule["confidence"]
                conf_valid, conf_errors = validate_field_structure(
                    confidence_value, confidence_rule, f"{field_name}_confidence"
                )
                valid = valid and conf_valid
                errors.extend(conf_errors)

            if score_value is not None and "score" in field_rule:
                score_rule = field_rule["score"]
                score_valid, score_errors = validate_field_structure(
                    score_value, score_rule, f"{field_name}_score"
                )
                valid = valid and score_valid
                errors.extend(score_errors)

            # Add field validation to report
            segment_validation["field_validations"][field_name] = {
                "valid": valid,
                "json_field_name": json_field_name,
                "errors": errors,
            }

            # Update segment validation status
            if not valid:
                segment_validation["valid"] = False

        # Add segment validation to report
        segments_validation.append(segment_validation)

        # Count valid segments
        if segment_validation["valid"]:
            valid_segments += 1

    # Create summary
    summary = {
        "total_segments": len(data["segments"]),
        "valid_segments": valid_segments,
        "invalid_segments": len(data["segments"]) - valid_segments,
        "overall_status": "PASS" if valid_segments == len(data["segments"]) else "FAIL",
    }

    # Create final report
    report = {
        "valid": valid_segments == len(data["segments"]),
        "segments_validation": segments_validation,
        "summary": summary,
    }

    return report


# Default YAML rules path
DEFAULT_RULES_PATH = "summary_validation_rules.yaml"


def validate_metadata(
    json_data: str, yaml_rules_path: str = DEFAULT_RULES_PATH
) -> Dict:
    """
    Wrapper function to validate video summary metadata JSON

    """
    return validate_video_summary(json_data, yaml_rules_path)


if __name__ == "__main__":
    import argparse

    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description="Validate video summary metadata JSON against YAML rules"
    )
    parser.add_argument(
        "json_file", help="Path to the JSON file containing video summary metadata"
    )
    parser.add_argument(
        "--rules",
        "-r",
        default=DEFAULT_RULES_PATH,
        help=f"Path to YAML rules file (default: {DEFAULT_RULES_PATH})",
    )
    parser.add_argument(
        "--output", "-o", help="Path to save the validation report (optional)"
    )

    args = parser.parse_args()

    # Read JSON data from file
    try:
        with open(args.json_file, "r") as file:
            json_data = file.read()
    except Exception as e:
        print(f"Error reading JSON file: {str(e)}")
        exit(1)

    # Validate the data
    validation_result = validate_metadata(json_data, args.rules)

    # Output the results
    if args.output:
        try:
            with open(args.output, "w") as file:
                json.dump(validation_result, file, indent=2)
            print(f"Validation report saved to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {str(e)}")
            print(json.dumps(validation_result, indent=2))
    else:
        # Print to console
        print(json.dumps(validation_result, indent=2))
