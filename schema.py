# schema.py

FIRESTORE_SCHEMA = {
    "flood_control_projects": {
        "fields": {
            "project_name": "string",
            "implementing_office": "string",
            "contractor": "string",
            "contract_cost": "number",
            "abc": "number",
            "region": "string",
            "status": "string",
            "date_started": "timestamp",
            "date_completed": "timestamp",
        }
    },
    "cpes_projects": {
        "fields": {
            "project_name": "string",
            "contractor": "string",
            "cpes_rating": "number",
        }
    },
    "contractor_name_mapping": {
        "fields": {
            "old_contractor_name": "string",
            "new_contractor_name": "string",
        }
    }
}
