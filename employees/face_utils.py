import face_recognition
import numpy as np
from io import BytesIO
from PIL import Image
import base64
import numpy as np
import face_recognition
from io import BytesIO

def imagefile_to_encoding(file_obj) -> list:
    """
    Accepts an image file object (InMemoryUploadedFile or bytes) and returns an encoding (list)
    Returns [] if no face is found.
    """
    try:
        if isinstance(file_obj, (bytes, bytearray)):
            img = face_recognition.load_image_file(BytesIO(file_obj))
        else:
            img = face_recognition.load_image_file(file_obj)

        encodings = face_recognition.face_encodings(img)
        if not encodings:
            return []  # return empty list instead of None
        return encodings[0].tolist()

    except Exception as e:
        print(f"⚠️ Error during face encoding: {e}")
        return []


def base64_to_encoding(b64_string) -> list:
    header, data = (b64_string.split(',',1) if ',' in b64_string else (None, b64_string))
    imgbytes = base64.b64decode(data)
    return imagefile_to_encoding(imgbytes)

def compare_encodings(known_encoding, unknown_encoding):
    """
    Return boolean match and distance (lower distance = better)
    """

    known = np.array(known_encoding)
    unknown = np.array(unknown_encoding)
    dist = np.linalg.norm(known - unknown)
    # threshold typical ~0.6 for face_recognition. 
    # Adjusted to 0.5 to balance strictness and usability.
    return (dist <= 0.5, float(dist))


import hashlib

def compute_md5(file_obj):
    """Compute MD5 hash of an uploaded image or file."""
    md5 = hashlib.md5()
    for chunk in file_obj.chunks() if hasattr(file_obj, 'chunks') else iter(lambda: file_obj.read(4096), b""):
        md5.update(chunk)
    file_obj.seek(0)  # Reset file pointer for reuse
    return md5.hexdigest()


