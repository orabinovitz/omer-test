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
                workflow_json = """<Your Workflow JSON Here>"""

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
