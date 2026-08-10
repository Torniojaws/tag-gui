from dataclasses import dataclass, field
from typing import List


@dataclass
class Playlist:
    name: str
    file_name: str
    tracks: List[str] = field(default_factory=list)
