from app.core.config import Settings


def test_local_runs_rewrite_docker_service_hostnames(monkeypatch):
    monkeypatch.delenv("USE_DOCKER_SERVICE_HOSTS", raising=False)

    settings = Settings(
        DATABASE_URL="postgresql://tutor:tutorpass@postgres:5432/tutordb",
        REDIS_URL="redis://redis:6379/0",
        QDRANT_URL="http://qdrant:6333",
    )

    assert settings.DATABASE_URL == "postgresql+psycopg://tutor:tutorpass@localhost:5432/tutordb"
    assert settings.REDIS_URL == "redis://localhost:6379/0"
    assert settings.QDRANT_URL == "http://localhost:6333"


def test_container_runs_keep_compose_service_hostnames(monkeypatch):
    monkeypatch.setenv("USE_DOCKER_SERVICE_HOSTS", "true")

    settings = Settings(
        DATABASE_URL="postgresql://tutor:tutorpass@postgres:5432/tutordb",
        REDIS_URL="redis://redis:6379/0",
        QDRANT_URL="http://qdrant:6333",
    )

    assert settings.DATABASE_URL == "postgresql+psycopg://tutor:tutorpass@postgres:5432/tutordb"
    assert settings.REDIS_URL == "redis://redis:6379/0"
    assert settings.QDRANT_URL == "http://qdrant:6333"
