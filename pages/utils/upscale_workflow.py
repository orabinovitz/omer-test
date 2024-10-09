def get_workflow_json():
    workflow_json = """
{
  "2": {
    "inputs": {
      "upscale_by": 2,
      "seed": 220252293484863,
      "steps": 8,
      "cfg": 7,
      "sampler_name": "dpmpp_3m_sde",
      "scheduler": "karras",
      "denoise": 0.4,
      "mode_type": "Linear",
      "tile_width": 1024,
      "tile_height": 1024,
      "mask_blur": 12,
      "tile_padding": 64,
      "seam_fix_mode": "None",
      "seam_fix_denoise": 0.3,
      "seam_fix_width": 160,
      "seam_fix_mask_blur": 32,
      "seam_fix_padding": 64,
      "force_uniform_tiles": "enable",
      "tiled_decode": false,
      "image": [
        "32",
        0
      ],
      "model": [
        "43",
        0
      ],
      "positive": [
        "3",
        0
      ],
      "negative": [
        "6",
        0
      ],
      "vae": [
        "8",
        2
      ],
      "upscale_model": [
        "5",
        0
      ]
    },
    "class_type": "UltimateSDUpscale",
    "_meta": {
      "title": "Ultimate SD Upscale"
    }
  },
  "3": {
    "inputs": {
      "strength": 0.7,
      "conditioning": [
        "7",
        0
      ],
      "control_net": [
        "4",
        0
      ],
      "image": [
        "32",
        0
      ]
    },
    "class_type": "ControlNetApply",
    "_meta": {
      "title": "Apply ControlNet"
    }
  },
  "4": {
    "inputs": {
      "control_net_name": "control_v11f1e_sd15_tile.pth"
    },
    "class_type": "ControlNetLoader",
    "_meta": {
      "title": "Load ControlNet Model"
    }
  },
  "5": {
    "inputs": {
      "model_name": "4x-UltraSharp.pth"
    },
    "class_type": "UpscaleModelLoader",
    "_meta": {
      "title": "Load Upscale Model"
    }
  },
  "6": {
    "inputs": {
      "text": "(worst quality, low quality:1.2)",
      "clip": [
        "17",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "Negative Prompt"
    }
  },
  "7": {
    "inputs": {
      "text": "",
      "clip": [
        "17",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "Positive Prompt"
    }
  },
  "8": {
    "inputs": {
      "ckpt_name": "Realistic_Vision_V5.1.safetensors"
    },
    "class_type": "CheckpointLoaderSimple",
    "_meta": {
      "title": "Load Checkpoint"
    }
  },
  "17": {
    "inputs": {
      "lora_name": "more_details.safetensors",
      "strength_model": 1,
      "strength_clip": 0,
      "model": [
        "8",
        0
      ],
      "clip": [
        "8",
        1
      ]
    },
    "class_type": "LoraLoader",
    "_meta": {
      "title": "Load LoRA"
    }
  },
  "31": {
    "inputs": {
      "filename_prefix": "ComfyUI",
      "images": [
        "41",
        0
      ]
    },
    "class_type": "SaveImage",
    "_meta": {
      "title": "Save Image"
    }
  },
  "32": {
    "inputs": {
      "image": "input.png",
      "upload": "image"
    },
    "class_type": "LoadImage",
    "_meta": {
      "title": "Load Image"
    }
  },
  "41": {
    "inputs": {
      "amount": 0.4,
      "image": [
        "2",
        0
      ]
    },
    "class_type": "ImageCASharpening+",
    "_meta": {
      "title": "🔧 Image Contrast Adaptive Sharpening"
    }
  },
  "43": {
    "inputs": {
      "b1": 1.05,
      "b2": 1.08,
      "s1": 0.9500000000000001,
      "s2": 0.8,
      "model": [
        "17",
        0
      ]
    },
    "class_type": "FreeU_V2",
    "_meta": {
      "title": "FreeU_V2"
    }
  }
}
    """
    return workflow_json