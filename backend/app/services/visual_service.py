from functools import lru_cache

import torch
from PIL import Image
from transformers import (
    BlipForConditionalGeneration,
    BlipProcessor,
)


VISION_MODEL_NAME = (
    "Salesforce/blip-image-captioning-base"
)
VISION_DEVICE = "cpu"


class VisualProcessingError(Exception):
    pass


@lru_cache(maxsize=1)
def get_visual_components() -> tuple:
    try:
        processor = BlipProcessor.from_pretrained(
            VISION_MODEL_NAME
        )

        model = (
            BlipForConditionalGeneration
            .from_pretrained(
                VISION_MODEL_NAME
            )
        )

        model.to(VISION_DEVICE)
        model.eval()

        return processor, model

    except Exception as exc:
        raise VisualProcessingError(
            "The visual-description model could not "
            "be downloaded or loaded."
        ) from exc


def get_visual_status() -> dict:
    return {
        "available": True,
        "engine": "BLIP image captioning",
        "model": VISION_MODEL_NAME,
        "device": VISION_DEVICE,
        "model_loaded": (
            get_visual_components.cache_info().currsize
            > 0
        ),
        "note": (
            "The model is downloaded and loaded during "
            "the first image or video analysis."
        ),
    }


def describe_pil_image(
    image: Image.Image,
) -> str:
    try:
        processor, model = get_visual_components()

        rgb_image = image.convert("RGB")

        inputs = processor(
            images=rgb_image,
            return_tensors="pt",
        )

        inputs = {
            key: value.to(VISION_DEVICE)
            for key, value in inputs.items()
        }

        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=50,
                num_beams=3,
            )

        description = processor.decode(
            generated_ids[0],
            skip_special_tokens=True,
        ).strip()

        return description

    except VisualProcessingError:
        raise

    except Exception as exc:
        raise VisualProcessingError(
            "The image could not be visually described."
        ) from exc