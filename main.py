import cv2
import os
import base64
import json
import threading
import time
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import gspread
from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()

# OpenAI API Key (Replace with your actual API key)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Google API setup
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
FOLDER_ID = os.getenv("FOLDER_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")



# version 7, trying to use fine tuned model 


# === Authenticate services ===
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=[
        "https://www.googleapis.com/auth/drive",
        "https://spreadsheets.google.com/feeds",
    ],
)
drive_service = build("drive", "v3", credentials=credentials)
gs_client = gspread.authorize(credentials)
sheet = gs_client.open_by_key(SPREADSHEET_ID).sheet1
client = OpenAI(api_key=OPENAI_API_KEY)

# === Camera Setup ===
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 9999)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 9999)
max_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
max_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera max resolution: {max_width}x{max_height}")

# === Viewport Config ===
base_width = 1920
base_height = 1080
rotation_angle = 0


def update_window_size():
    if rotation_angle in [90, 270]:
        cv2.resizeWindow("Camera Feed", base_height, base_width)
    else:
        cv2.resizeWindow("Camera Feed", base_width, base_height)


# === State ===
photo_success_timer = 0
multi_photo_mode = False
capture_stage = "idle"
current_job = {"label_images": [], "contents_image": None, "timestamp": None}
current_sheet_row = None
sheet_lock = threading.Lock()
label_phase_complete = False
label_ready_event = threading.Event()
status_message = ""
status_lock = threading.Lock()
status_display_timer = 0
input_locked = False
input_lock = threading.Lock()


# === Helper Functions ===
def set_status_message(message, duration_frames=100, unlock_input=False):
    global status_message, status_display_timer, input_locked
    with status_lock:
        status_message = message
        status_display_timer = duration_frames
    if unlock_input:
        with input_lock:
            input_locked = False


def rotate_image(image, angle):
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def upload_image_to_drive(file_path, folder_id=FOLDER_ID):
    file_name = os.path.basename(file_path)
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype="image/jpeg")
    uploaded_file = (
        drive_service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    drive_service.permissions().create(
        fileId=uploaded_file["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()
    return f"https://drive.google.com/uc?id={uploaded_file['id']}"


def stitch_images_vertically(image_paths, output_path):
    """
    Stitches the list of images (given by file paths) vertically into one image.
    Writes the stitched result to `output_path`.
    """
    images = [cv2.imread(p) for p in image_paths]

    # Compute the max width and total height
    max_width = max(img.shape[1] for img in images)
    total_height = sum(img.shape[0] for img in images)

    # Create the stitched image
    stitched = cv2.resize(images[0], (max_width, images[0].shape[0]))
    current_y = images[0].shape[0]

    for img in images[1:]:
        # Resize each image to the max width
        resized_img = cv2.resize(img, (max_width, img.shape[0]))
        # Vertically append
        stitched = cv2.vconcat([stitched, resized_img])
        current_y += resized_img.shape[0]

    cv2.imwrite(output_path, stitched)


def process_images(image_paths):
    """
    Sends the provided image(s) to GPT-4 for OCR analysis
    (structured shipping label extraction).
    """
    encoded_images = []
    for path in image_paths:
        with open(path, "rb") as img_file:
            encoded_images.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}",
                        "detail": "high",
                    },
                }
            )

    response = client.chat.completions.create(
        model="ft:gpt-4o-2024-08-06:professor-color:label-ocr-v1:BMQMApWX",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a MILLION DOLLAR OCR SMART SHIPPING LABEL READER.\n"
                    "You see package label images and must extract the following fields:\n"
                    " • sender_name\n"
                    " • sender_company\n"
                    " • sender_address\n"
                    " • sender_phone\n"
                    " • recipient_name\n"
                    " • recipient_company\n"
                    " • recipient_phone\n"
                    " • recipient_address\n"
                    " • tracking_details (array of {carrier, tracking_number})\n\n"
                    "Important Rules:\n"
                    " 1. Phone fields must contain digits only. If unclear, use 'NA'.\n"
                    " 2. For tracking numbers, preserve digits and letters exactly. Never replace 0 with O or O with 0. If unreadable, use 'NA'.\n"
                    " 3. If any other field is unreadable, set that field to 'NA'.\n\n"
                    "Typically the recipient address will be 4870 Adohr Lane Ste A Camarillo CA, 93012.\n"
                    "Ensure that you identify the correct sender and recipient as the recipient will always be the same.\n\n"
                    "Return the data by calling the function 'extract_package_details' using the JSON object with the properties:\n"
                    "  sender_name, sender_company, sender_phone, sender_address,\n"
                    "  recipient_name, recipient_company, recipient_phone, recipient_address,\n"
                    "  tracking_details (array of carrier/tracking_number)."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract structured data from these package label images.",
                    }
                ]
                + encoded_images,
            },
        ],
        functions=[
            {
                "name": "extract_package_details",
                "description": "Extracts label data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sender_name": {"type": "string"},
                        "sender_company": {"type": "string"},
                        "sender_phone": {"type": "string"},
                        "sender_address": {"type": "string"},
                        "recipient_name": {"type": "string"},
                        "recipient_company": {"type": "string"},
                        "recipient_phone": {"type": "string"},
                        "recipient_address": {"type": "string"},
                        "tracking_details": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "carrier": {"type": "string"},
                                    "tracking_number": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": [
                        "sender_name",
                        "sender_company",
                        "sender_address",
                        "sender_phone",
                        "recipient_name",
                        "recipient_company",
                        "recipient_address",
                        "recipient_phone",
                        "tracking_details",
                    ],
                },
            }
        ],
        function_call={"name": "extract_package_details"},
    )
    return json.loads(response.choices[0].message.function_call.arguments)


def append_partial_row(data, label_urls):
    """
    Appends a row to the Google Sheet with the label details.
    """
    global current_sheet_row, label_phase_complete
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.get("sender_name"),
        data.get("sender_company"),
        data.get("sender_phone"),
        data.get("sender_address"),
        data.get("recipient_name"),
        data.get("recipient_company"),
        data.get("recipient_phone"),
        data.get("recipient_address"),
    ]
    tracking = data.get("tracking_details", [])
    for i in range(2):
        if i < len(tracking):
            row.append(tracking[i].get("tracking_number", ""))
            row.append(tracking[i].get("carrier", ""))
        else:
            row += ["", ""]
    row.append(", ".join(label_urls))
    row.append("")  # For the contents URL

    with sheet_lock:
        current_sheet_row = len(sheet.get_all_values()) + 1
        sheet.append_row(row)
        label_phase_complete = True
        label_ready_event.set()
        set_status_message("Partial row written to Google Sheets.")
    print("📝 Partial row written to Google Sheets.")


def update_sheet_row(row_index, contents_url):
    """
    Updates the existing row with the contents photo URL.
    """
    try:
        sheet.update_cell(row_index, 15, contents_url)
        set_status_message("Box contents URL updated in sheet.", unlock_input=True)
        print("✅ Box contents URL updated in sheet.")
    except Exception as e:
        set_status_message("Sheet update failed", unlock_input=True)
        print(f"❌ Failed to update contents URL: {e}")


def handle_label_phase(job):
    """
    Handles the label portion of the workflow (upload to Drive, stitching if multiple photos).
    """
    try:
        label_ready_event.clear()
        set_status_message("Uploading and processing label...")

        # If there are multiple label images (e.g. wrap-around label),
        # stitch them vertically into one final image.
        stitched_path = None
        if len(job["label_images"]) > 1:
            stitched_path = f"stitched_label_{job['timestamp']}.jpg"
            stitch_images_vertically(job["label_images"], stitched_path)
            final_label_paths = [stitched_path]
        else:
            # Only one label image
            final_label_paths = [job["label_images"][0]]

        # Upload stitched or single label image
        label_urls = [upload_image_to_drive(p) for p in final_label_paths]

        # Process them as a single entity
        result = process_images(final_label_paths)

        # Append to Google Sheets
        append_partial_row(result, label_urls)

        # Remove local label image files
        for p in job["label_images"]:
            os.remove(p)
        if stitched_path and os.path.exists(stitched_path):
            os.remove(stitched_path)

    except Exception as e:
        set_status_message("Label phase failed")
        print(f"❌ Label phase failed: {e}")


def handle_contents_phase(job):
    """
    Waits for the label phase to finish, then uploads the box contents photo and updates the sheet row.
    """
    global current_sheet_row
    print("⏳ Waiting for label phase to complete...")
    set_status_message("Waiting for label phase to complete...")
    label_ready_event.wait(timeout=15)

    if not label_ready_event.is_set():
        set_status_message("Label phase timeout", unlock_input=True)
        print("❌ Contents phase aborted: label thread did not signal ready.")
        return

    try:
        set_status_message("Uploading contents photo...")
        contents_url = upload_image_to_drive(job["contents_image"])
        update_sheet_row(current_sheet_row, contents_url)
        os.remove(job["contents_image"])
    except Exception as e:
        set_status_message("Contents phase failed", unlock_input=True)
        print(f"❌ Contents phase failed: {e}")


# === Init Display ===
if not camera.isOpened():
    print("Error: Could not open camera.")
    exit()

cv2.namedWindow("Camera Feed", cv2.WINDOW_NORMAL)
update_window_size()

while True:
    ret, frame = camera.read()
    if not ret:
        print("Failed to grab frame")
        break

    rotated_frame = rotate_image(frame, rotation_angle)
    if rotation_angle in [0, 180]:
        display_frame = cv2.resize(rotated_frame, (base_width, base_height))
    else:
        display_frame = cv2.resize(rotated_frame, (base_height, base_width))

    overlay = display_frame.copy()

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(
        overlay,
        "[SPACE] Capture  |  [M] Multi-Photo Mode",
        (60, 40),
        font,
        0.8,
        (0, 255, 0),
        2,
    )
    cv2.putText(
        overlay,
        f"[O/P] Rotate Left/Right  |  Rotation: {rotation_angle}",
        (60, 70),
        font,
        0.8,
        (0, 255, 0),
        2,
    )

    if capture_stage == "contents":
        cv2.putText(
            overlay,
            "Take photo of BOX CONTENTS now",
            (60, 110),
            font,
            1.0,
            (255, 200, 0),
            3,
        )
    elif capture_stage == "label2":
        cv2.putText(
            overlay,
            "Multi-Photo: Take second LABEL photo",
            (60, 110),
            font,
            1.0,
            (0, 255, 255),
            3,
        )
    elif capture_stage == "label1":
        cv2.putText(
            overlay, "Take LABEL photo", (60, 110), font, 1.0, (255, 255, 255), 3
        )

    # Display "PHOTO SUCCESSFUL" briefly
    if photo_success_timer > 0:
        cv2.putText(
            overlay,
            "PHOTO SUCCESSFUL",
            (overlay.shape[1] // 2 - 200, overlay.shape[0] // 2),
            font,
            2,
            (0, 255, 0),
            4,
        )
        photo_success_timer -= 1

    # Display status message
    with status_lock:
        if status_display_timer > 0:
            cv2.putText(
                overlay,
                status_message,
                (60, overlay.shape[0] - 80),
                font,
                0.9,
                (0, 255, 255),
                2,
            )
            status_display_timer -= 1

    # Display input-locked notification
    with input_lock:
        if input_locked:
            cv2.putText(
                overlay,
                "Processing... Input is temporarily disabled",
                (60, overlay.shape[0] - 40),
                font,
                0.9,
                (0, 100, 255),
                2,
            )

    cv2.imshow("Camera Feed", overlay)
    key = cv2.waitKey(1) & 0xFF

    if key == 27:  # ESC
        break
    elif key == ord("o"):
        rotation_angle = (rotation_angle - 90) % 360
        update_window_size()
    elif key == ord("p"):
        rotation_angle = (rotation_angle + 90) % 360
        update_window_size()
    elif key in [ord("m"), 32]:  # 'm' or SPACE
        with input_lock:
            if input_locked:
                continue

        if key == ord("m"):
            # User explicitly wants multi-photo mode
            multi_photo_mode = True
            capture_stage = "label1"
            current_job = {
                "label_images": [],
                "contents_image": None,
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            }
            print("Multi-photo mode activated.")

        elif key == 32:
            # SPACE pressed
            if capture_stage == "idle":
                # Not in multi-photo mode, just proceed with single label -> contents flow
                multi_photo_mode = False
                capture_stage = "label1"
                current_job = {
                    "label_images": [],
                    "contents_image": None,
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                }

            timestamp = current_job["timestamp"]

            # Capture label or contents photo
            if capture_stage.startswith("label"):
                fname = f"label_{timestamp}_{len(current_job['label_images']) + 1}.jpg"
                cv2.imwrite(fname, rotated_frame)
                current_job["label_images"].append(fname)

                # If multi-photo mode: wait for second label image if we just took the first
                if multi_photo_mode and len(current_job["label_images"]) == 1:
                    capture_stage = "label2"
                else:
                    capture_stage = "contents"
                    # Handle label in a separate thread
                    threading.Thread(
                        target=handle_label_phase, args=(current_job.copy(),)
                    ).start()

            elif capture_stage == "contents":
                fname = f"contents_{timestamp}.jpg"
                cv2.imwrite(fname, rotated_frame)
                current_job["contents_image"] = fname

                # Lock input while contents is processed
                with input_lock:
                    input_locked = True
                # Handle contents in a separate thread
                threading.Thread(
                    target=handle_contents_phase, args=(current_job.copy(),)
                ).start()

                capture_stage = "idle"

            photo_success_timer = 20

camera.release()
cv2.destroyAllWindows()