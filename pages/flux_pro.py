import streamlit as st
import os
import replicate
import requests

# Set page configuration
st.set_page_config(
    page_title="Flux Pro 1.1",
    page_icon="🎨",
    layout="centered",
)

st.title("🎨 Flux Pro 1.1")

# Get the API key from Streamlit secrets
api_key = st.secrets["REPLICATE_API_TOKEN"]
os.environ["REPLICATE_API_TOKEN"] = api_key

# Hide Streamlit footer and add custom CSS
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    .aspect-ratio-selectbox {width: 200px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Prompt input
prompt = st.text_area("Enter your prompt", height=100)

# Aspect ratio selection
st.subheader("Select Aspect Ratio")
aspect_ratios = ["1:1", "16:9", "3:2", "4:3", "5:4", "4:5", "Custom"]
selected_ratio = st.selectbox("Aspect Ratio", aspect_ratios)

# Orientation toggle
if selected_ratio != "1:1":
    orientation = st.radio(
        "Orientation",
        ("Horizontal", "Vertical"),
        horizontal=True,
        help="Select the orientation of the image",
    )
else:
    orientation = "Square"

# Custom width and height
if selected_ratio == "Custom":
    st.subheader("Custom Dimensions")
    col1, col2 = st.columns(2)
    with col1:
        width = st.number_input("Width (px)", min_value=100, max_value=4096, value=1024)
    with col2:
        height = st.number_input("Height (px)", min_value=100, max_value=4096, value=1024)
else:
    # Map aspect ratios to dimensions
    ratio_map = {
        "1:1": (1, 1),
        "16:9": (16, 9),
        "3:2": (3, 2),
        "4:3": (4, 3),
        "5:4": (5, 4),
        "4:5": (4, 5),
    }
    ratio = ratio_map[selected_ratio]
    if orientation == "Vertical":
        ratio = (ratio[1], ratio[0])
    width, height = ratio
    # Scale dimensions to a standard size
    scale = 512 / max(width, height)
    width = int(width * scale)
    height = int(height * scale)

# Prompt upsampling toggle
prompt_upsampling = st.checkbox("Enable Prompt Upsampling", value=False)

# Generate button
if st.button("🎨 Generate Image"):
    with st.spinner("Generating image..."):
        try:
            output = replicate.run(
                "black-forest-labs/flux-1.1-pro",
                input={
                    "width": width,
                    "height": height,
                    "prompt": prompt,
                    "aspect_ratio": "custom",
                    "output_format": "png",
                    "output_quality": 100,
                    "safety_tolerance": 5,
                    "prompt_upsampling": prompt_upsampling,
                },
            )

            if output and isinstance(output, str):
                st.success("Image generation complete!")
                st.image(output, caption="Generated Image", use_column_width=True)

                # Download button
                response = requests.get(output)
                if response.status_code == 200:
                    img_data = response.content
                    st.download_button(
                        label="💾 Download Generated Image",
                        data=img_data,
                        file_name="generated_image.png",
                        mime="image/png",
                    )
                else:
                    st.error("Failed to retrieve the generated image.")

                # Upscale option
                if st.button("✨ Upscale Image"):
                    with st.spinner("Upscaling image..."):
                        # Read the image data
                        data = base64.b64encode(img_data).decode("utf-8")
                        input_file = f"data:image/png;base64,{data}"

                        # Use the same workflow_json as in the upscaler
                        workflow_json = """<Your Workflow JSON Here>"""

                        upscaled_output = replicate.run(
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

                        if upscaled_output and isinstance(upscaled_output, list):
                            upscaled_url = upscaled_output[0]
                            st.success("Upscaling complete!")
                            st.image(
                                upscaled_url, caption="Upscaled Image", use_column_width=True
                            )

                            # Download upscaled image
                            response = requests.get(upscaled_url)
                            if response.status_code == 200:
                                upscaled_img_data = response.content
                                st.download_button(
                                    label="💾 Download Upscaled Image",
                                    data=upscaled_img_data,
                                    file_name="upscaled_image.png",
                                    mime="image/png",
                                )
                            else:
                                st.error("Failed to retrieve the upscaled image.")
                        else:
                            st.error("Failed to upscale the image.")

            else:
                st.error("Failed to generate the image.")

        except replicate.exceptions.ModelError as e:
            st.error(f"Model Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
else:
    st.info("Enter a prompt and adjust settings to generate an image.")
