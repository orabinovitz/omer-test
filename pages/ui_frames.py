import streamlit as st
import requests
import os
import sys
import toml
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import cv2  # OpenCV for face detection
from io import BytesIO

# Set page config
st.set_page_config(page_title="📱 UI Frame Generator", page_icon="📱", layout="wide")

# Title is now set only once, in the page config
# Remove the following line:
# st.title("📱 UI Frame Generator")

# Function to get the file key from Figma file URL
def get_file_key(figma_file_url):
    try:
        if 'file/' in figma_file_url:
            parts = figma_file_url.split('file/')[1]
            file_key = parts.split('/')[0]
        elif 'figma.com/' in figma_file_url:
            parts = figma_file_url.split('figma.com/')[1]
            file_key = parts.split('/')[0]
        else:
            raise ValueError("URL format not recognized")
        
        if not file_key or file_key == "design":
            raise ValueError("Invalid file key extracted")
        
        return file_key
    except Exception as e:
        st.error(f"Error extracting file key: {str(e)}")
        st.error(f"Provided URL: {figma_file_url}")
        st.stop()

# Function to get the file structure from Figma API
def get_file_structure(file_key, figma_api_token):
    headers = {
        'X-Figma-Token': figma_api_token
    }
    url = f'https://api.figma.com/v1/files/{file_key}'
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        st.error(f"Error fetching file: {response.text}")
        st.error(f"Status code: {response.status_code}")
        st.error(f"File key: {file_key}")
        st.error(f"API token (first 5 chars): {figma_api_token[:5]}...")
        st.stop()
    return response.json()

# Function to find layers matching the search term
def find_matching_layers(document, search_term, page_name):
    matching_layers = []
    def traverse(node):
        if node['name'] == page_name and 'children' in node:
            for frame in node['children']:
                if frame['type'] == 'FRAME' and 'children' in frame:
                    for child in frame['children']:
                        if search_term.lower() in child['name'].lower():
                            matching_layers.append(child)
        for child in node.get('children', []):
            traverse(child)
    traverse(document)
    return matching_layers

# Function to get image URLs for the layers
def get_layer_images(file_key, node_ids, figma_api_token):
    headers = {
        'X-Figma-Token': figma_api_token
    }
    params = {
        'ids': ','.join(node_ids),
        'format': 'png',
        'scale': 2  # Adjust scale as needed
    }
    url = f'https://api.figma.com/v1/images/{file_key}'
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        st.error(f"Error fetching images: {response.text}")
        st.stop()
    return response.json().get('images', {})

# Function to create drop shadow
def create_drop_shadow(image, opacity, offset_x, offset_y, blur_radius, shadow_spread):
    width = image.width + abs(offset_x) + 2 * (blur_radius + shadow_spread)
    height = image.height + abs(offset_y) + 2 * (blur_radius + shadow_spread)
    shadow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    shadow_layer = Image.new('RGBA', (image.width + 2*shadow_spread, image.height + 2*shadow_spread), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.rectangle([shadow_spread, shadow_spread, image.width + shadow_spread, image.height + shadow_spread], 
                          fill=(0, 0, 0, int(255 * opacity)))
    shadow.paste(shadow_layer, (blur_radius + max(offset_x, 0), 
                                blur_radius + max(offset_y, 0)), 
                 shadow_layer)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    result.paste(shadow, (0, 0), shadow)
    result.paste(image, (blur_radius + shadow_spread + max(-offset_x, 0),
                         blur_radius + shadow_spread + max(-offset_y, 0)),
                 image)
    return result

# Function to add rounded corners
def add_rounded_corners(image, radius):
    rounded_mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(rounded_mask)
    draw.rounded_rectangle(
        [(0, 0), image.size],
        radius=radius,
        fill=255
    )
    image.putalpha(rounded_mask)
    return image

# Load the Haar cascade for face detection
@st.cache_resource
def load_haar_cascade():
    haar_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(haar_cascade_path)
    return face_cascade

# Function to resize image for preview
def resize_image_for_preview(image, preview_width=300):
    aspect_ratio = image.height / image.width
    preview_height = int(preview_width * aspect_ratio)
    preview_image = image.copy()
    preview_image.thumbnail((preview_width, preview_height), Image.LANCZOS)
    return preview_image

# Main app function
def main():
    st.title("📱 UI Frame Generator")

    # Find the secrets file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    secrets_path = os.path.join(parent_dir, ".streamlit", "secrets.toml")

    # Load secrets from the file
    try:
        with open(secrets_path, "r") as f:
            secrets = toml.load(f)
        figma_api_token = secrets["FIGMA_API_TOKEN"]
        figma_file_url = secrets.get("FIGMA_FILE_URL", "")
        page_name = secrets.get("PAGE_NAME", "Screens")
    except FileNotFoundError:
        st.error("Secrets file not found. Please make sure it exists in the correct location.")
        st.stop()
    except KeyError as e:
        st.error(f"Required secret {e} not found in the secrets file.")
        st.stop()

    if not figma_file_url:
        st.error("Figma file URL not provided in secrets.")
        st.stop()

    # Step 1: User Uploads an Image
    uploaded_file = st.file_uploader("Upload an image:", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        user_image = Image.open(uploaded_file).convert("RGBA")
        # Resize the image for preview only
        preview_width = 300  # You can adjust this value as needed
        aspect_ratio = user_image.height / user_image.width
        preview_height = int(preview_width * aspect_ratio)
        preview_image = user_image.copy()
        preview_image.thumbnail((preview_width, preview_height), Image.LANCZOS)
        st.image(preview_image, caption="Uploaded Image", use_column_width=False)

    # Step 2: User Input for Feature Search
    search_term = st.text_input("Enter the feature name to search for layers:")
    if not search_term:
        st.info("Please enter a search term to find layers.")
        return

    # Step 3: Fetch and Display Matching Layers
    file_key = get_file_key(figma_file_url)
    
    try:
        file_data = get_file_structure(file_key, figma_api_token)
    except Exception as e:
        st.error(f"Error occurred while fetching file structure: {str(e)}")
        st.stop()

    matching_layers = find_matching_layers(file_data['document'], search_term, page_name)

    # Fetch all layer images upfront
    if not matching_layers:
        st.warning("No matching layers found.")
        return

    # Use st.session_state to store fetched images
    if 'layer_images' not in st.session_state:
        with st.spinner("Fetching layer images..."):
            node_ids = [layer['id'] for layer in matching_layers]
            image_urls = get_layer_images(file_key, node_ids, figma_api_token)
            
            layer_images = {}
            for layer_id, image_url in image_urls.items():
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    layer_images[layer_id] = Image.open(BytesIO(image_response.content))
            
            st.session_state.layer_images = layer_images
    else:
        layer_images = st.session_state.layer_images

    # Display and select matching layers
    st.subheader("Select a Layer")

    if not matching_layers:
        st.warning("No matching layers found.")
        return

    # Use st.session_state to store fetched images
    if 'layer_images' not in st.session_state:
        with st.spinner("Fetching layer images..."):
            node_ids = [layer['id'] for layer in matching_layers]
            image_urls = get_layer_images(file_key, node_ids, figma_api_token)
            
            layer_images = {}
            for layer_id, image_url in image_urls.items():
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    layer_images[layer_id] = Image.open(BytesIO(image_response.content))
            
            st.session_state.layer_images = layer_images
    else:
        layer_images = st.session_state.layer_images

    # Create a list of layer options for the radio button
    layer_options = [layer['name'] for layer in matching_layers]

    # Use a radio button for layer selection
    selected_layer_name = st.radio("Choose a layer:", layer_options)

    # Find the selected layer
    selected_layer = next((layer for layer in matching_layers if layer['name'] == selected_layer_name), None)

    if selected_layer:
        st.success(f"Selected layer: {selected_layer['name']}")
        selected_layer_id = selected_layer['id']
        selected_layer_image = layer_images[selected_layer_id]
        
        # Display the selected layer image
        preview_image = resize_image_for_preview(selected_layer_image)
        st.image(preview_image, use_column_width=False, caption=f"Preview: {selected_layer['name']}")
    else:
        st.info("Please select a layer to proceed.")
        return

    # Step 5: Background Color Picker
    canvas_bg_color = st.color_picker("Pick a background color:", "#ffecf5")

    # Step 6: Process and Generate the Canvas
    if st.button("Generate Canvas"):
        if uploaded_file is None:
            st.error("Please upload an image before generating the canvas.")
            return

        with st.spinner("Processing image..."):
            try:
                # Canvas dimensions
                canvas_width = 1600
                canvas_height = 897

                # Corner radius for rounded corners
                corner_radius = 30

                # Face position ratios
                face_x_ratio = 0.5  # Horizontal position (0 to 1)
                face_y_ratio = 0.4  # Vertical position (0 to 1)

                # Load UI image (selected layer image)
                ui_image = selected_layer_image.convert("RGBA")
                alpha = ui_image.getchannel('A')
                bbox = alpha.getbbox()
                if bbox:
                    ui_image = ui_image.crop(bbox)
                    alpha = alpha.crop(bbox)
                else:
                    st.error("The UI image is completely transparent.")
                    st.stop()

                width, height = ui_image.size
                alpha_np = np.array(alpha)
                opaque_threshold = 128

                # Find the bottom edge of the top UI
                in_top_ui = False
                top_ui_end = None
                for i in range(height):
                    row = alpha_np[i]
                    if not in_top_ui:
                        if np.any(row >= opaque_threshold):
                            in_top_ui = True
                    else:
                        if np.all(row < opaque_threshold):
                            top_ui_end = i
                            break
                if top_ui_end is None:
                    top_ui_end = 0

                # Find the top edge of the bottom UI
                in_bottom_ui = False
                bottom_ui_start = None
                for i in range(height - 1, -1, -1):
                    row = alpha_np[i]
                    if not in_bottom_ui:
                        if np.any(row >= opaque_threshold):
                            in_bottom_ui = True
                    else:
                        if np.all(row < opaque_threshold):
                            bottom_ui_start = i + 1
                            break
                if bottom_ui_start is None:
                    bottom_ui_start = height

                # Compute the central transparent area
                central_top = top_ui_end
                central_bottom = bottom_ui_start
                central_height = central_bottom - central_top
                central_width = width

                if central_height <= 0:
                    st.error("No central transparent area found between top and bottom UI.")
                    st.stop()

                # Load the user's uploaded image
                person_image = user_image
                person_width, person_height = person_image.size

                # Detect face in the person image
                person_image_cv = cv2.cvtColor(np.array(person_image), cv2.COLOR_RGBA2RGB)
                face_cascade = load_haar_cascade()
                gray = cv2.cvtColor(person_image_cv, cv2.COLOR_RGB2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
                if len(faces) == 0:
                    st.error("No face detected in the uploaded image.")
                    st.stop()
                (x, y, w, h) = faces[0]
                face_center_x = x + w // 2
                face_center_y = y + h // 2

                # Desired face position in central area
                desired_face_x_in_central = central_width * face_x_ratio
                desired_face_y_in_central = central_height * face_y_ratio

                # Calculate scale factors
                scale_factor_y_top = desired_face_y_in_central / face_center_y
                scale_factor_y_bottom = (central_height - desired_face_y_in_central) / (person_height - face_center_y)
                scale_factor_y = max(scale_factor_y_top, scale_factor_y_bottom)
                scale_factor_x_left = desired_face_x_in_central / face_center_x
                scale_factor_x_right = (central_width - desired_face_x_in_central) / (person_width - face_center_x)
                scale_factor_x = max(scale_factor_x_left, scale_factor_x_right)
                scale_factor = max(scale_factor_y, scale_factor_x, central_height / person_height, central_width / person_width)

                # Resize the person's image
                new_person_width = int(person_width * scale_factor)
                new_person_height = int(person_height * scale_factor)
                person_image_resized = person_image.resize((new_person_width, new_person_height), Image.LANCZOS)

                # Adjust face coordinates
                face_center_x_scaled = int(face_center_x * scale_factor)
                face_center_y_scaled = int(face_center_y * scale_factor)

                # Calculate position to place the person image
                person_x = desired_face_x_in_central - face_center_x_scaled
                person_y = central_top + desired_face_y_in_central - face_center_y_scaled

                # Ensure the person image covers the central area completely
                if person_x > 0:
                    person_x = 0
                if person_x + new_person_width < width:
                    person_x = width - new_person_width
                if person_y > central_top:
                    person_y = central_top
                if person_y + new_person_height < central_bottom:
                    person_y = central_bottom - new_person_height

                # Create a new image for the positioned person image
                person_image_positioned = Image.new("RGBA", (width, height))
                person_image_positioned.paste(person_image_resized, (int(person_x), int(person_y)), person_image_resized)

                # UI background fill color
                ui_bg_fill_color = "#f3f4f7"
                ui_bg_fill = Image.new("RGBA", ui_image.size, ui_bg_fill_color)

                # Composite the person's image onto the background fill
                ui_bg_fill = Image.alpha_composite(ui_bg_fill, person_image_positioned)

                # Overlay the UI image onto the background fill
                ui_bg_fill.paste(ui_image, (0, 0), ui_image)

                # The combined image is now the screen component
                screen_component = ui_bg_fill

                # Scale the screen component
                screen_width, screen_height = screen_component.size
                scale_factor_canvas = 0.88 * canvas_height / screen_height
                new_screen_width = int(screen_width * scale_factor_canvas)
                new_screen_height = int(screen_height * scale_factor_canvas)
                screen_component_resized = screen_component.resize((new_screen_width, new_screen_height), Image.LANCZOS)

                # Apply rounded corners
                screen_component_rounded = add_rounded_corners(screen_component_resized, corner_radius)

                # Add drop shadow
                shadow_opacity = 0.65
                shadow_offset_x = 0
                shadow_offset_y = 25
                shadow_blur = 25
                shadow_spread = 10
                screen_component_with_shadow = create_drop_shadow(screen_component_rounded, shadow_opacity, shadow_offset_x, shadow_offset_y, shadow_blur, shadow_spread)

                # Create the canvas
                canvas = Image.new("RGBA", (canvas_width, canvas_height), canvas_bg_color)
                screen_x = (canvas_width - screen_component_with_shadow.width) // 2
                screen_y = (canvas_height - screen_component_with_shadow.height) // 2
                canvas.paste(screen_component_with_shadow, (screen_x, screen_y), screen_component_with_shadow)

                # Display the output image
                st.image(canvas, caption="Generated Canvas", use_column_width=True)

                # Provide a download button
                buffered = BytesIO()
                canvas.save(buffered, format="PNG")
                st.download_button(
                    label="Download Image",
                    data=buffered.getvalue(),
                    file_name="output.png",
                    mime="image/png"
                )
            except Exception as e:
                st.error(f"An error occurred: {e}")

if __name__ == '__main__':
    main()