import streamlit as st
import os
import base64
import replicate
import requests

# Set page configuration
st.set_page_config(
    page_title="Image Upscaler",
    page_icon="🖼️",
    layout="centered",
)

st.title("🖼️ Image Upscaler")

# Get the API key from Streamlit secrets
api_key = st.secrets["REPLICATE_API_TOKEN"]
os.environ["REPLICATE_API_TOKEN"] = api_key

# Hide Streamlit footer and style
hide_streamlit_style = """
    <style>
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# File uploader
uploaded_file = st.file_uploader(
    "Drag and drop an image to upscale", type=["png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    # Display the uploaded image
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

    # Read the file and encode it as a data URI
    data = base64.b64encode(uploaded_file.read()).decode("utf-8")
    input_file = f"data:image/png;base64,{data}"

    if st.button("✨ Upscale Image"):
        with st.spinner("Upscaling image..."):
            try:
                # Define the workflow_json (paste your entire JSON here)
                workflow_json = """{\n  \"2\": {\n    \"inputs\": {\n      \"upscale_by\": 2,\n      \"seed\": 830015891849899,\n      \"steps\": 8,\n      \"cfg\": 7,\n      \"sampler_name\": \"dpmpp_3m_sde\",\n      \"scheduler\": \"karras\",\n      \"denoise\": 0.4,\n      \"mode_type\": \"Linear\",\n      \"tile_width\": 1024,\n      \"tile_height\": 1024,\n      \"mask_blur\": 12,\n      \"tile_padding\": 64,\n      \"seam_fix_mode\": \"None\",\n      \"seam_fix_denoise\": 0.3,\n      \"seam_fix_width\": 160,\n      \"seam_fix_mask_blur\": 32,\n      \"seam_fix_padding\": 64,\n      \"force_uniform_tiles\": \"enable\",\n      \"tiled_decode\": false,\n      \"image\": [\n        \"44\",\n        0\n      ],\n      \"model\": [\n        \"43\",\n        0\n      ],\n      \"positive\": [\n        \"3\",\n        0\n      ],\n      \"negative\": [\n        \"6\",\n        0\n      ],\n      \"vae\": [\n        \"8\",\n        2\n      ],\n      \"upscale_model\": [\n        \"5\",\n        0\n      ]\n    },\n    \"class_type\": \"UltimateSDUpscale\",\n    \"_meta\": {\n      \"title\": \"Ultimate SD Upscale\"\n    }\n  },\n  \"3\": {\n    \"inputs\": {\n      \"strength\": 0.7000000000000001,\n      \"conditioning\": [\n        \"7\",\n        0\n      ],\n      \"control_net\": [\n        \"4\",\n        0\n      ],\n      \"image\": [\n        \"32\",\n        0\n      ]\n    },\n    \"class_type\": \"ControlNetApply\",\n    \"_meta\": {\n      \"title\": \"Apply ControlNet\"\n    }\n  },\n  \"4\": {\n    \"inputs\": {\n      \"control_net_name\": \"control_v11f1e_sd15_tile.pth\"\n    },\n    \"class_type\": \"ControlNetLoader\",\n    \"_meta\": {\n      \"title\": \"Load ControlNet Model\"\n    }\n  },\n  \"5\": {\n    \"inputs\": {\n      \"model_name\": \"4x-UltraSharp.pth\"\n    },\n    \"class_type\": \"UpscaleModelLoader\",\n    \"_meta\": {\n      \"title\": \"Load Upscale Model\"\n    }\n  },\n  \"6\": {\n    \"inputs\": {\n      \"text\": \"(worst quality, low quality:1.2)\",\n      \"clip\": [\n        \"17\",\n        1\n      ]\n    },\n    \"class_type\": \"CLIPTextEncode\",\n    \"_meta\": {\n      \"title\": \"Negative Prompt\"\n    }\n  },\n  \"7\": {\n    \"inputs\": {\n      \"text\": \"\",\n      \"clip\": [\n        \"17\",\n        1\n      ]\n    },\n    \"class_type\": \"CLIPTextEncode\",\n    \"_meta\": {\n      \"title\": \"Positive Prompt\"\n    }\n  },\n  \"8\": {\n    \"inputs\": {\n      \"ckpt_name\": \"Realistic_Vision_V6.0_NV_B1.safetensors\"\n    },\n    \"class_type\": \"CheckpointLoaderSimple\",\n    \"_meta\": {\n      \"title\": \"Load Checkpoint\"\n    }\n  },\n  \"17\": {\n    \"inputs\": {\n      \"lora_name\": \"more_details.safetensors\",\n      \"strength_model\": 1,\n      \"strength_clip\": 0,\n      \"model\": [\n        \"8\",\n        0\n      ],\n      \"clip\": [\n        \"8\",\n        1\n      ]\n    },\n    \"class_type\": \"LoraLoader\",\n    \"_meta\": {\n      \"title\": \"Load LoRA\"\n    }\n  },\n  \"31\": {\n    \"inputs\": {\n      \"filename_prefix\": \"ComfyUI\",\n      \"images\": [\n        \"41\",\n        0\n      ]\n    },\n    \"class_type\": \"SaveImage\",\n    \"_meta\": {\n      \"title\": \"Save Image\"\n    }\n  },\n  \"32\": {\n    \"inputs\": {\n      \"image\": \"input.png\",\n      \"upload\": \"image\"\n    },\n    \"class_type\": \"LoadImage\",\n    \"_meta\": {\n      \"title\": \"Load Image\"\n    }\n  },\n  \"41\": {\n    \"inputs\": {\n      \"amount\": 0.4,\n      \"image\": [\n        \"2\",\n        0\n      ]\n    },\n    \"class_type\": \"ImageCASharpening+\",\n    \"_meta\": {\n      \"title\": \"🔧 Image Contrast Adaptive Sharpening\"\n    }\n  },\n  \"43\": {\n    \"inputs\": {\n      \"b1\": 1.05,\n      \"b2\": 1.08,\n      \"s1\": 0.9500000000000001,\n      \"s2\": 0.8,\n      \"model\": [\n        \"17\",\n        0\n      ]\n    },\n    \"class_type\": \"FreeU_V2\",\n    \"_meta\": {\n      \"title\": \"FreeU_V2\"\n    }\n  },\n  \"44\": {\n    \"inputs\": {\n      \"guide_size\": 768,\n      \"guide_size_for\": true,\n      \"max_size\": 1024,\n      \"seed\": 89639468963531,\n      \"steps\": 8,\n      \"cfg\": 7,\n      \"sampler_name\": \"dpmpp_3m_sde\",\n      \"scheduler\": \"karras\",\n      \"denoise\": 0.3,\n      \"feather\": 5,\n      \"noise_mask\": true,\n      \"force_inpaint\": true,\n      \"bbox_threshold\": 0.35000000000000003,\n      \"bbox_dilation\": 10,\n      \"bbox_crop_factor\": 3,\n      \"sam_detection_hint\": \"center-1\",\n      \"sam_dilation\": 0,\n      \"sam_threshold\": 0.93,\n      \"sam_bbox_expansion\": 0,\n      \"sam_mask_hint_threshold\": 0.7,\n      \"sam_mask_hint_use_negative\": \"False\",\n      \"drop_size\": 10,\n      \"wildcard\": \"\",\n      \"cycle\": 1,\n      \"inpaint_model\": false,\n      \"noise_mask_feather\": 20,\n      \"image\": [\n        \"32\",\n        0\n      ],\n      \"model\": [\n        \"43\",\n        0\n      ],\n      \"clip\": [\n        \"17\",\n        1\n      ],\n      \"vae\": [\n        \"8\",\n        2\n      ],\n      \"positive\": [\n        \"7\",\n        0\n      ],\n      \"negative\": [\n        \"6\",\n        0\n      ],\n      \"bbox_detector\": [\n        \"45\",\n        0\n      ]\n    },\n    \"class_type\": \"FaceDetailer\",\n    \"_meta\": {\n      \"title\": \"FaceDetailer\"\n    }\n  },\n  \"45\": {\n    \"inputs\": {\n      \"model_name\": \"bbox/face_yolov8m.pt\"\n    },\n    \"class_type\": \"UltralyticsDetectorProvider\",\n    \"_meta\": {\n      \"title\": \"UltralyticsDetectorProvider\"\n    }\n  }\n}"""

                output = replicate.run(
                    "fofr/any-comfyui-workflow:ca6589497a1d31922ec4e2b7c4d17d4a168bc6ac6d0971b2c8c60fc3de0fee4b",
                    input={
                        "input_file": input_file,
                        "output_format": "png",
                        "workflow_json": workflow_json,
                        "output_quality": 100,
                        "randomise_seeds": True,
                        "force_reset_cache": False,
                        "return_temp_files": True,
                    },
                )

                # Output is a list of URLs
                if output and isinstance(output, list):
                    output_url = output[0]
                    st.success("Upscaling complete!")
                    st.image(output_url, caption="Upscaled Image", use_column_width=True)

                    # Download button
                    response = requests.get(output_url)
                    if response.status_code == 200:
                        img_data = response.content
                        st.download_button(
                            label="💾 Download Upscaled Image",
                            data=img_data,
                            file_name="upscaled_image.png",
                            mime="image/png",
                        )
                    else:
                        st.error("Failed to retrieve the upscaled image.")
                else:
                    st.error("Failed to upscale the image.")

            except replicate.exceptions.ModelError as e:
                st.error(f"Model Error: {str(e)}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
else:
    st.info("Please upload an image to upscale.")
