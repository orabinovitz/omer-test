import streamlit as st
import os
import sys
import base64
import replicate
import requests
import toml
from streamlit_image_comparison import image_comparison
from PIL import Image
import io

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Now import the workflow module
from pages.utils.workflow import get_workflow_json

# Set page configuration
st.set_page_config(
    page_title="Image Upscaler",
    page_icon="🖼️",
    layout="centered",
)

st.title("🖼️ Image Upscaler")

# Get the API key from Streamlit secrets
secrets_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml"
)
with open(secrets_path, "r") as f:
    secrets = toml.load(f)
api_key = secrets["REPLICATE_API_TOKEN"]
os.environ["REPLICATE_API_TOKEN"] = api_key

# File uploader
uploaded_file = st.file_uploader(
    "Drag and drop an image to upscale", type=["png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    # Open the uploaded image using Pillow
    image = Image.open(uploaded_file)
    
    # Display the uploaded image
    st.image(image, caption="Uploaded Image", use_column_width=True)

    # Convert the image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    # Encode the image as a data URI
    data = base64.b64encode(img_byte_arr).decode("utf-8")
    input_file = f"data:image/png;base64,{data}"

    if st.button("✨ Upscale Image"):
        with st.spinner("Upscaling image..."):
            try:
                output = replicate.run(
                    "fofr/any-comfyui-workflow:ca6589497a1d31922ec4e2b7c4d17d4a168bc6ac6d0971b2c8c60fc3de0fee4b",
                    input={
                        "input_file": input_file,
                        "output_format": "png",
                        "workflow_json": get_workflow_json(),
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
                        img1=image,
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
                            data=img_byte_arr,
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
else:
    st.info("Please upload an image to upscale.")
