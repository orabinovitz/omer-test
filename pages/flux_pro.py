import streamlit as st
import os
import sys
import replicate
import requests
import base64
import toml
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
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
    /* Modal styles */
    .modal {
        display: none; 
        position: fixed; 
        z-index: 1000; 
        padding-top: 60px; 
        left: 0;
        top: 0;
        width: 100%; 
        height: 100%; 
        overflow: auto; 
        background-color: rgba(0,0,0,0.9); 
    }
    .modal-content {
        margin: auto;
        display: block;
        width: 80%;
        max-width: 700px;
    }
    .close {
        position: absolute;
        top: 30px;
        right: 35px;
        color: #f1f1f1;
        font-size: 40px;
        font-weight: bold;
        transition: 0.3s;
        z-index: 1001;
    }
    .close:hover,
    .close:focus {
        color: #bbb;
        text-decoration: none;
        cursor: pointer;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state variables
if 'generated_image_urls' not in st.session_state:
    st.session_state.generated_image_urls = []
if 'generated_image_data' not in st.session_state:
    st.session_state.generated_image_data = []
if 'show_upscale_button' not in st.session_state:
    st.session_state.show_upscale_button = False

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

# Number of images slider
num_images = st.slider("Number of images to generate", min_value=1, max_value=10, value=1)

# Generate button
if st.button("🎨 Generate Images"):
    with st.spinner("Generating images..."):
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

            # Function to generate a single image
            def generate_image_call():
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
                return output

            # Use ThreadPoolExecutor to run multiple API calls concurrently
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(generate_image_call) for _ in range(num_images)]
                outputs = [future.result() for future in futures]

            # Check if outputs are valid
            if outputs and all(isinstance(output, str) for output in outputs):
                st.success("Image generation complete!")
                st.session_state.generated_image_urls = outputs

                # Store the generated image data for download
                st.session_state.generated_image_data = []
                for image_url in outputs:
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        img_data = response.content
                        st.session_state.generated_image_data.append(img_data)
                    else:
                        st.error(f"Failed to retrieve the generated image at {image_url}.")

                # Show download button for all images
                zip_file = io.BytesIO()
                with zipfile.ZipFile(zip_file, 'w') as zipf:
                    for idx, img_data in enumerate(st.session_state.generated_image_data):
                        zipf.writestr(f"generated_image_{idx+1}.png", img_data)
                zip_file.seek(0)
                st.download_button(
                    label="💾 Download All Generated Images",
                    data=zip_file,
                    file_name="generated_images.zip",
                    mime="application/zip",
                )

                # Upscale option
                st.session_state.show_upscale_button = True

            else:
                st.error("Failed to generate the images.")

        except replicate.exceptions.ModelError as e:
            st.error(f"Model Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
else:
    st.info("Enter a prompt and adjust settings to generate images.")

# Display generated images if available
if st.session_state.generated_image_urls:
    # Display images in a grid
    num_cols = 3  # Number of columns in the grid
    image_urls = st.session_state.generated_image_urls
    st.subheader("Generated Images")
    rows = [image_urls[i:i + num_cols] for i in range(0, len(image_urls), num_cols)]
    for row_idx, row in enumerate(rows):
        cols = st.columns(num_cols)
        for idx, image_url in enumerate(row):
            col = cols[idx]
            # Generate a safe key using the index
            image_idx = row_idx * num_cols + idx
            # Create an HTML block with a modal popup
            html_code = f'''
            <div>
                <a href="#modal-{image_idx}">
                    <img src="{image_url}" style="width:100%; height:auto; cursor: pointer;"/>
                </a>
                <div id="modal-{image_idx}" class="modal">
                    <span class="close" onclick="document.getElementById('modal-{image_idx}').style.display='none'">&times;</span>
                    <img class="modal-content" src="{image_url}">
                </div>
            </div>
            <script>
                var modal = document.getElementById("modal-{image_idx}");
                var img = document.querySelector("img[src='{image_url}']");
                img.onclick = function() {{
                    modal.style.display = "block";
                }}
            </script>
            '''
            col.markdown(html_code, unsafe_allow_html=True)
            # Add a checkbox for selecting the image to upscale
            col.checkbox("Select for Upscaling", key=f"select_{image_idx}")

# Upscale button
if st.session_state.get('show_upscale_button', False):
    if st.button("✨ Upscale Selected Images"):
        # Collect selected images
        selected_indices = [idx for idx in range(len(st.session_state.generated_image_urls)) if st.session_state.get(f"select_{idx}", False)]
        if not selected_indices:
            st.warning("Please select at least one image to upscale.")
        else:
            with st.spinner("Upscaling images..."):
                try:
                    # Collect the image data for selected images
                    selected_image_data = [st.session_state.generated_image_data[idx] for idx in selected_indices]
                    selected_image_urls = [st.session_state.generated_image_urls[idx] for idx in selected_indices]

                    # Function to upscale a single image
                    def upscale_image(image_data):
                        data = base64.b64encode(image_data).decode("utf-8")
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
                        return output

                    # Use ThreadPoolExecutor to run multiple upscaling calls concurrently
                    with ThreadPoolExecutor() as executor:
                        futures = [executor.submit(upscale_image, image_data) for image_data in selected_image_data]
                        upscaled_outputs = [future.result() for future in futures]

                    # Output is a list of lists of URLs (since the upscaling output is a list)
                    upscaled_image_urls = []
                    for output in upscaled_outputs:
                        if output and isinstance(output, list):
                            upscaled_image_urls.append(output[0])  # Get the first URL
                        else:
                            upscaled_image_urls.append(None)  # Or handle errors appropriately

                    # Display the upscaled images along with originals
                    st.success("Upscaling complete!")
                    for idx, (original_idx, upscaled_url) in enumerate(zip(selected_indices, upscaled_image_urls)):
                        st.write(f"Image {original_idx+1}")
                        original_url = st.session_state.generated_image_urls[original_idx]
                        if upscaled_url:
                            image_comparison(
                                img1=original_url,
                                img2=upscaled_url,
                                label1="Original Image",
                                label2="Upscaled Image",
                                width=700
                            )
                            # Download buttons for both images
                            col1, col2 = st.columns(2)
                            with col1:
                                orig_data = st.session_state.generated_image_data[original_idx]
                                st.download_button(
                                    label="💾 Download Original Image",
                                    data=orig_data,
                                    file_name=f"original_image_{original_idx+1}.png",
                                    mime="image/png",
                                )
                            with col2:
                                response = requests.get(upscaled_url)
                                if response.status_code == 200:
                                    upscaled_img_data = response.content
                                    st.download_button(
                                        label="💾 Download Upscaled Image",
                                        data=upscaled_img_data,
                                        file_name=f"upscaled_image_{original_idx+1}.png",
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