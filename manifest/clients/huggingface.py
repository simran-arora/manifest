"""Hugging Face client."""
import logging
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from manifest.clients.client import Client
from manifest.request import LMRequest, Request

logger = logging.getLogger(__name__)


class HuggingFaceClient(Client):
    """HuggingFace client."""

    # User param -> (client param, default value)
    PARAMS = {
        "temperature": ("temperature", 1.0),
        "max_tokens": ("max_tokens", 10),
        "n": ("n", 1),
        "top_p": ("top_p", 1.0),
        "top_k": ("top_k", 50),
        "repetition_penalty": ("repetition_penalty", 1.0),
        "do_sample": ("do_sample", True),
        "client_timeout": ("client_timeout", 120),  # seconds
    }
    REQUEST_CLS = LMRequest

    def connect(
        self,
        connection_str: Optional[str] = None,
        client_args: Dict[str, Any] = {},
    ) -> None:
        """
        Connect to the HuggingFace url.

        Arsg:
            connection_str: connection string.
            client_args: client arguments.
        """
        if not connection_str:
            raise ValueError("Must provide connection string")
        self.host = connection_str.rstrip("/")
        for key in self.PARAMS:
            setattr(self, key, client_args.pop(key, self.PARAMS[key][1]))

    def close(self) -> None:
        """Close the client."""
        pass

    def get_generation_url(self) -> str:
        """Get generation URL."""
        return self.host + "/completions"

    def get_generation_header(self) -> Dict[str, str]:
        """
        Get generation header.

        Returns:
            header.
        """
        return {}

    def supports_batch_inference(self) -> bool:
        """Return whether the client supports batch inference."""
        return True

    def get_model_params(self) -> Dict:
        """
        Get model params.

        By getting model params from the server, we can add to request
        and make sure cache keys are unique to model.

        Returns:
            model params.
        """
        res = requests.post(self.host + "/params")
        return res.json()

    def get_score_prompt_request(
        self,
        request: Request,
    ) -> Tuple[Callable[[], Dict], Dict]:
        """
        Get the logit score of the prompt via a forward pass of the model.

        Args:
            request: request.

        Returns:
            request function that takes no input.
            request parameters as dict.
        """
        request_params = request.to_dict(self.PARAMS)
        retry_timeout = request_params.pop("client_timeout")
        # Do not add params like we do with request as the model isn't sampling
        request_params = {"prompt": request.prompt}

        def _run_completion() -> Dict:
            post_str = self.host + "/score_sequence"
            try:
                res = requests.post(
                    post_str,
                    json=request_params,
                    timeout=retry_timeout,
                )
                res.raise_for_status()
            except requests.Timeout as e:
                logger.error("HF request timed out. Increase client_timeout.")
                raise e
            except requests.exceptions.HTTPError as e:
                logger.error(res.text)
                raise e
            return res.json()

        return _run_completion, request_params
