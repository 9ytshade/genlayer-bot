# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class CanaryCVision(gl.Contract):
    """Vision canary: the rendered image, not page text/URL, is the evidence."""

    outcome: str

    def __init__(self):
        self.outcome = "PENDING"

    @gl.public.write
    def evaluate_page(self, url: str) -> str:
        def leader_fn() -> dict:
            try:
                screenshot = gl.nondet.web.render(url, mode="screenshot")
                result = gl.nondet.exec_prompt(
                    "Inspect the supplied screenshot only. Return JSON with exactly one key, outcome, "
                    "set to RENDERED when an image is present; otherwise INCONCLUSIVE.",
                    images=[screenshot],
                    response_format="json",
                )
            except Exception:
                return {"outcome": "INCONCLUSIVE"}
            if isinstance(result, dict) and result.get("outcome") == "RENDERED":
                return {"outcome": "RENDERED"}
            return {"outcome": "INCONCLUSIVE"}

        result = gl.eq_principle.prompt_comparative(
            leader_fn,
            principle=(
                "Independently verify that the declared bounded outcome is supported by the same "
                "rendered image. Never use page text or a URL in place of the image."
            ),
        )
        self.outcome = "RENDERED" if result.get("outcome") == "RENDERED" else "INCONCLUSIVE"
        return self.outcome

    @gl.public.view
    def get_outcome(self) -> str:
        return self.outcome
