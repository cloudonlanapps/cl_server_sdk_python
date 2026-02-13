import pytest
import pytest_asyncio
from tests.test_utils import AuthConfig

@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_store_entities(
    request: pytest.FixtureRequest,
    auth_config: AuthConfig,
    created_entities: set[int],
):
    """Clean up all store entities before store integration tests run.

    Runs only for test_store_integration.py and other integration tests in this folder.
    Uses CLI-provided auth credentials.
    """
    # All integration tests in this folder use the store
    import logging
    # logging.info(f"Cleaning up store for module: {request.module.__name__}")

    # Skip cleanup if no auth (cannot delete entities)
    if not auth_config.username:
        yield
        return

    # Bulk cleanup logic
    try:
        if not auth_config.username or not auth_config.password:
             yield
             return

        username = auth_config.username
        password = auth_config.password
        auth_url = auth_config.auth_url
        compute_url = auth_config.compute_url
        store_url = auth_config.store_url
        mqtt_url = auth_config.mqtt_url

        from cl_client import ServerPref, SessionManager

        config = ServerPref(
            auth_url=auth_url,
            compute_url=compute_url,
            store_url=store_url,
            mqtt_url=mqtt_url,
        )
        
        async with SessionManager(server_pref=config) as session:
            await session.login(username, password)
            async with session.create_store_manager() as mgr:
                # 1. Try to delete specifically tracked entities first
                if created_entities:
                    # logging.info(f"Cleaning up {len(created_entities)} tracked entities...")
                    # Copy set to avoid modification during iteration
                    ids_to_delete = list(created_entities)
                    for entity_id in ids_to_delete:
                        try:
                            # Use force=True to handle soft-deletion automatically
                            # We need to await this
                            await mgr.delete_entity(entity_id, force=True)
                        except Exception as e:
                            # logging.warning(f"Failed to delete tracked entity {entity_id}: {e}")
                            pass
                        created_entities.discard(entity_id)
                    
                    # logging.info("Tracked cleanup complete.")

    except Exception as e:
        # Non-fatal cleanup failure
        import logging
        logging.warning(f"Cleanup failed: {e}")

    yield
