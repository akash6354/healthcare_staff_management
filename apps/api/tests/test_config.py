"""Provider connection strings (Render, Heroku-style) are converted for asyncpg."""

from app.core.config import Settings


def test_render_postgres_urls_are_normalised() -> None:
    v = Settings._asyncpg_url(
        "postgres://u:p@dpg-x.singapore-postgres.render.com/oglos?sslmode=require"
    )
    assert v == "postgresql+asyncpg://u:p@dpg-x.singapore-postgres.render.com/oglos?ssl=require"
    assert (
        Settings._asyncpg_url("postgresql://u:p@dpg-x/oglos")
        == "postgresql+asyncpg://u:p@dpg-x/oglos"
    )
    already = "postgresql+asyncpg://u:p@localhost:5434/oglos"
    assert Settings._asyncpg_url(already) == already
