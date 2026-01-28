"""Type definitions for the CoLAN client SDK."""

from typing import Final, override


class Unset:
    """Sentinel class for unset values.
    
    Used to distinguish between None (meaning "set to null" or "no value")
    and unset (meaning "do not update").
    """
    
    def __bool__(self) -> bool:
        return False
        
    @override
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final[Unset] = Unset()
