from .models import UserSetting
from .database import db


# Settings helpers
def get_user_settings(user_id=1):
    """
    Retrieves user settings from the database.
    For now, we'll use a default user_id of 1.
    """
    return UserSetting.query.filter_by(user_id=user_id).first()


def save_user_settings(data, user_id=1):
    """
    Saves user settings to the database.
    """
    settings = get_user_settings(user_id)
    if not settings:
        settings = UserSetting(user_id=user_id)

    settings.courtlistener_api_key = data.get("courtlistener_api_key")
    settings.courtlistener_com_api_endpoint = data.get("courtlistener_com_api_endpoint")
    settings.california_codes_url = data.get("california_codes_url")
    settings.gemini_api_key = data.get("gemini_api_key")
    settings.google_api_endpoint = data.get("google_api_endpoint")
    settings.verifypdf_api_key = data.get("verifypdf_api_key")
    settings.verify_pdf_endpoint = data.get("verify_pdf_endpoint")
    settings.riza_key = data.get("riza_key")
    settings.neo4j_uri = data.get("neo4j_uri")
    settings.neo4j_username = data.get("neo4j_username")
    settings.neo4j_password = data.get("neo4j_password")
    settings.neo4j_database = data.get("neo4j_database")
    settings.aura_instance_id = data.get("aura_instance_id")
    settings.aura_instance_name = data.get("aura_instance_name")
    settings.gcp_project_id = data.get("gcp_project_id")
    settings.gcp_vertex_ai_data_store_id = data.get("gcp_vertex_ai_data_store_id")
    settings.gcp_vertex_ai_search_app = data.get("gcp_vertex_ai_search_app")
    settings.gcp_service_account_key = data.get("gcp_service_account_key")
    settings.theme = data.get("theme")
    settings.voice_engine = data.get("voice_engine")
    settings.voice_model = data.get("voice_model")
    db.session.add(settings)
    db.session.commit()
    return settings


def get_feature_flags(user_id=1):
    """Return persisted feature flags for ``user_id``."""
    settings = get_user_settings(user_id)
    return settings.feature_flags if settings and settings.feature_flags else {}


def save_feature_flags(flags, user_id=1):
    """Persist feature flags for ``user_id``."""
    settings = get_user_settings(user_id)
    if not settings:
        settings = UserSetting(user_id=user_id, feature_flags={})
    current = settings.feature_flags or {}
    current.update({k: bool(v) for k, v in flags.items()})
    settings.feature_flags = current
    db.session.add(settings)
    db.session.commit()
    return current
