import streamlit as st
import qrcode
from PIL import Image
import io

# Set page configuration
st.set_page_config(
    page_title="QR Code Generator",
    page_icon="🔲",
    layout="centered",
)

st.title("🔲 QR Code Generator")

# Input field for the link
link = st.text_input("Enter the link you want to convert to a QR code:")

# Always show the Generate QR Code button
if st.button("✨ Generate QR Code"):
    if link:
        with st.spinner("Generating QR code..."):
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(link)
            qr.make(fit=True)
            
            # Create an image from the QR code
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # Convert the image to bytes
            img_byte_arr = io.BytesIO()
            qr_image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            st.success("QR code generated successfully!")
            
            # Display the QR code
            st.image(img_byte_arr, caption="Generated QR Code", use_column_width=True)
            
            # Download button for the QR code
            st.download_button(
                label="💾 Download QR Code",
                data=img_byte_arr,
                file_name="qr_code.png",
                mime="image/png",
            )
    else:
        st.warning("Please enter a link to generate a QR code.")