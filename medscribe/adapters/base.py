from abc import ABC, abstractmethod
from medscribe.schemas import Transcript, SOAPNoteDraft


class BaseModelAdapter(ABC):
    """
    Abstract interface for SOAP note extraction adapters.
    Ensures decoupled local inference (e.g. Ollama, Mock, MLX, llama.cpp).
    """

    @abstractmethod
    def generate_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        """
        Extracts structured draft SOAP note with claim citations from transcript.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Returns True if the engine/model is operational locally.
        """
        pass

    @abstractmethod
    def engine_name(self) -> str:
        """
        Returns the descriptive name and model identifier.
        """
        pass
