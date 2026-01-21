"""Concurrency integration tests for store service."""

import asyncio
import concurrent.futures
import uuid
from pathlib import Path as PathlibPath

import pytest
from cl_client import StoreManager, SessionManager
from conftest import AuthConfig, get_expected_error, should_succeed

# Helper to run async function in a new loop (for threading)
def run_async(coro):
    return asyncio.run(coro)

def _create_collection_worker(base_url, auth_url, username, password, idx):
    """Worker to create a collection."""
    async def task():
        # Create fresh session and manager
        async with SessionManager(base_url=auth_url) as session:
            # Login if creds provided
            if username and password:
                await session.login(username, password)
            
            # Use manual client construction to set higher timeout
            from cl_client import JWTAuthProvider
            from cl_client.store_client import StoreClient
            
            token = session.get_token() if session.is_authenticated() else None
            auth_provider = JWTAuthProvider(token=token) if token else None
            
            async with StoreClient(base_url=base_url, auth_provider=auth_provider, timeout=60.0) as client:
                manager = StoreManager(client)
                
                label = f"ConcTest_{idx}_{uuid.uuid4().hex[:6]}"
                result = await manager.create_entity(label=label, is_collection=True)
                return {"success": result.is_success, "error": result.error, "id": result.data.id if result.is_success else None}

    return asyncio.run(task())

def _read_worker(base_url, auth_url, username, password):
    """Worker to read entities."""
    async def task():
        async with SessionManager(base_url=auth_url) as session:
            if username and password:
                await session.login(username, password)
            
            # Use manual client construction to set higher timeout
            from cl_client import JWTAuthProvider
            from cl_client.store_client import StoreClient
            
            token = session.get_token() if session.is_authenticated() else None
            auth_provider = JWTAuthProvider(token=token) if token else None
            
            async with StoreClient(base_url=base_url, auth_provider=auth_provider, timeout=60.0) as client:
                manager = StoreManager(client)
                result = await manager.list_entities(page_size=10)
                return {"success": result.is_success, "error": result.error}

    return asyncio.run(task())


@pytest.mark.integration
def test_concurrent_collection_creation(cli_config, auth_config):
    """Test concurrent collection creation (Write-Write concurrency)."""
    # Skip if we don't have write permissions
    if not should_succeed(auth_config, "store_write"):
        pytest.skip("No store_write permission")

    base_url = cli_config.store_url
    username = cli_config.username
    password = cli_config.password
    auth_url = auth_config.auth_url

    CONCURRENCY = 10
    created_ids = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(_create_collection_worker, base_url, auth_url, username, password, i)
            for i in range(CONCURRENCY)
        ]
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            assert res["success"], f"Failed: {res['error']}"
            if res["id"]:
                created_ids.append(res["id"])

    # Cleanup (best effort)
    # We use a single manager to cleanup
    async def cleanup():
        async with SessionManager(base_url=auth_url) as session:
            if username and password:
                await session.login(username, password)
            manager = session.create_store_manager()
            for eid in created_ids:
                await manager.delete_entity(eid)
    
    asyncio.run(cleanup())


@pytest.mark.integration
def test_concurrent_read_operations(cli_config, auth_config):
    """Test concurrent read operations (Read-Read concurrency)."""
    if not should_succeed(auth_config, "store_read"):
        pytest.skip("No store_read permission")

    base_url = cli_config.store_url
    username = cli_config.username
    password = cli_config.password
    auth_url = auth_config.auth_url

    CONCURRENCY = 20
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(_read_worker, base_url, auth_url, username, password)
            for i in range(CONCURRENCY)
        ]
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            assert res["success"], f"Read failed: {res['error']}"


@pytest.mark.integration
def test_mixed_concurrent_operations(cli_config, auth_config):
    """Test mixed operations (Read-Write concurrency)."""
    if not should_succeed(auth_config, "store_write"):
        pytest.skip("No store_write permission")

    base_url = cli_config.store_url
    username = cli_config.username
    password = cli_config.password
    auth_url = auth_config.auth_url
    
    CONCURRENCY = 10
    created_ids = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        # Mix of reads and writes
        futures = []
        for i in range(CONCURRENCY):
            if i % 2 == 0:
                futures.append(executor.submit(_create_collection_worker, base_url, auth_url, username, password, i))
            else:
                futures.append(executor.submit(_read_worker, base_url, auth_url, username, password))
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            assert res["success"], f"Operation failed: {res.get('error')}"
            if res.get("id"):
                created_ids.append(res["id"])

    # Cleanup
    async def cleanup():
        async with SessionManager(base_url=auth_url) as session:
            if username and password:
                await session.login(username, password)
            manager = session.create_store_manager()
            for eid in created_ids:
                await manager.delete_entity(eid)
    
    asyncio.run(cleanup())
