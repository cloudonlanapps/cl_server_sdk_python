from cl_client.store_client import StoreClient
import pytest


@pytest.mark.asyncio
async def test_store_client_uninitialized_errors():
    """Test that StoreClient methods raise RuntimeError when not initialized."""
    client = StoreClient()
    
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.health_check()
        
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.list_entities()
        
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.read_entity(1)
        
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.get_versions(1)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.create_entity(is_collection=True)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.update_entity(1, is_collection=True, label="test")

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.patch_entity(1)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.delete_entity(1)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.delete_all_entities()

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.get_pref()

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.update_guest_mode(True)

        

