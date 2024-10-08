import streamlit as st
import os
import sys
import replicate
import requests
import base64
import toml
from streamlit_image_comparison import image_comparison

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Now import the workflow module
from pages.utils.workflow import get_workflow_json  # Change this line

# Set page configuration
st.set_page_config(
    page_title="Flux Pro 1.1",
    page_icon="🎨",
    layout="centered",
)

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

st.title("🎨 Flux Pro 1.1")

# Get the API key from Streamlit secrets
secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.streamlit', 'secrets.toml')
with open(secrets_path, 'r') as f:
    secrets = toml.load(f)
api_key = secrets["REPLICATE_API_TOKEN"]
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
aspect_ratios = ["16:9", "1:1", "3:2", "4:3", "5:4", "4:5", "Custom"]
selected_ratio = st.selectbox("Aspect Ratio", aspect_ratios, index=0)

# Orientation toggle
if selected_ratio != "1:1":
    orientation = st.radio(
        "Orientation",
        ("Landscape", "Portrait"),
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
        width = st.number_input("Width (px)", min_value=256, max_value=1440, value=1024)
    with col2:
        height = st.number_input("Height (px)", min_value=256, max_value=1440, value=1024)
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
    
    # Calculate dimensions based on the maximum allowed dimension (1440)
    max_dimension = 1440
    if orientation == "Landscape" or (selected_ratio == "1:1" and ratio[0] >= ratio[1]):
        width = max_dimension
        height = int(width * ratio[1] / ratio[0])
        if height > max_dimension:
            height = max_dimension
            width = int(height * ratio[0] / ratio[1])
    else:  # Portrait orientation
        height = max_dimension
        width = int(height * ratio[0] / ratio[1])
        if width > max_dimension:
            width = max_dimension
            height = int(width * ratio[1] / ratio[0])
    
    # Ensure minimum dimension is at least 256
    if width < 256:
        width = 256
        height = int(width * ratio[1] / ratio[0])
    if height < 256:
        height = 256
        width = int(height * ratio[0] / ratio[1])

# Prompt upsampling toggle
prompt_upsampling = st.checkbox("Enable Prompt Upsampling", value=True)

# Generate button
if st.button("🎨 Generate Image"):
    with st.spinner("Generating image..."):
        try:
            # Determine the correct aspect ratio string for the API
            if selected_ratio == "Custom":
                api_aspect_ratio = "custom"
            elif orientation == "Portrait" and selected_ratio != "1:1":
                # Invert the aspect ratio for portrait orientation
                w, h = selected_ratio.split(":")
                api_aspect_ratio = f"{h}:{w}"
            else:
                api_aspect_ratio = selected_ratio

            output = replicate.run(
                "black-forest-labs/flux-1.1-pro",
                input={
                    "width": width,
                    "height": height,
                    "prompt": prompt,
                    "aspect_ratio": api_aspect_ratio,
                    "output_format": "png",
                    "output_quality": 100,
                    "safety_tolerance": 5,
                    "prompt_upsampling": prompt_upsampling,
                },
            )

            if output and isinstance(output, str):
                st.success("Image generation complete!")
                st.session_state.generated_image_url = output
                st.session_state.generated_image = st.image(output, caption="Generated Image", use_column_width=True)

                # Download button
                response = requests.get(output)
                if response.status_code == 200:
                    img_data = response.content
                    st.session_state.generated_image_data = img_data
                    st.session_state.download_button = st.download_button(
                        label="💾 Download Generated Image",
                        data=img_data,
                        file_name="generated_image.png",
                        mime="image/png",
                    )
                else:
                    st.error("Failed to retrieve the generated image.")

                # Upscale option
                st.session_state.show_upscale_button = True

            else:
                st.error("Failed to generate the image.")

        except replicate.exceptions.ModelError as e:
            st.error(f"Model Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
else:
    st.info("Enter a prompt and adjust settings to generate an image.")

# Upscale button (outside the Generate Image button block)
if st.session_state.get('show_upscale_button', False):
    if st.button("✨ Upscale Image"):
        with st.spinner("Upscaling image..."):
            try:
                # Read the image data
                img_data = st.session_state.generated_image_data
                data = base64.b64encode(img_data).decode("utf-8")
                input_file = f"data:image/png;base64,{data}"

                # Get the workflow_json from workflow.py
                workflow_json = get_workflow_json()

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
                    
                    # Use image_comparison widget
                    image_comparison(
                        img1=st.session_state.generated_image_url,
                        img2=output_url,
                        label1="Original Image",
                        label2="Upscaled Image",
                        width=700
                    )

                    # Download buttons for both images
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            label="💾 Download Original Image",
                            data=st.session_state.generated_image_data,
                            file_name="original_image.png",
                            mime="image/png",
                        )
                    with col2:
                        response = requests.get(output_url)
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

            except replicate.exceptions.ModelError as e:
                st.error(f"Model Error: {str(e)}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                