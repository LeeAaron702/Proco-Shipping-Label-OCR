# Professor Color Inbound OCR - Smart Shipping Label Reader

## Overview
This project is a smart OCR system designed for warehouse environments and small reselling companies to capture shipping label information and log it into Google Sheets, using OpenAI as a smart OCR for text extraction and Google Drive for image hosting.

Built for a family-run warehouse, this system is packaged with a simple UI and is designed to be run by anyone with a webcam and a Windows 11 PC. It can be integrated into your operations with a single double-click.

## 🚀 Features
- Automatic capture of shipping labels and box contents using a webcam
- Multi-photo mode for labels that wrap around boxes
- OCR powered by OpenAI (fine-tuned GPT-4o model)
- Google Drive image upload
- Google Sheets row creation and update
- Asynchronous threading to prevent delays or blocking
- Real-time visual feedback via OpenCV overlay
- Automatic update from GitHub on each run

---

## 📁 Folder Setup and Files
Your working folder should include:
- `main.py` — The OCR application
- `run.bat` — The launcher that updates and runs the app
- `requirements.txt` — All required Python dependencies
- `.env` — Your local environment variables
- `.env.example` — A template for safe sharing
- `README.md` — This file

---

## 🔧 Requirements
- Windows 11 PC
- A webcam (ideally 4K, minimum 1080p)
- Python 3.10+
- Git for Windows
- OpenAI account with API key
- Google Cloud project with Sheets & Drive API enabled

---

## 📦 Google Setup Instructions

### 1. Create a Google Cloud Project
- Visit [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project

### 2. Enable APIs
In the left sidebar:
- Go to **APIs & Services > Library**
- Enable **Google Drive API**
- Enable **Google Sheets API**

### 3. Create a Service Account
- Go to **IAM & Admin > Service Accounts**
- Create a new service account
- Assign "Editor" role
- After creation, click **Add Key → JSON**
- Download the JSON file and place it in your project folder

### 4. Share Access
- Go to your Google Drive and Google Sheet
- Share both with the **client email** from the JSON file

### 5. Get the Folder and Spreadsheet ID
- **Folder ID**: Open your Drive folder → Copy the string after `/folders/`
- **Spreadsheet ID**: Open your Sheet → Copy the string between `/d/` and `/edit`
- **Spreadsheet URL**: Copy the full share link for start script to open

---

## 📑 Google Sheet Template
Before using, create a Google Sheet utilizing the example csv
- Example CSV For Sheets.csv
- The column headers should follow 
```
 Date and Time	Sender Name	Sender Company	Sender Phone	Sender Address	Recipient Name	Recipient Company	Recipient Phone	Recipient Address	Tracking #1	Carrier #1	Tracking #2	Carrier #2	Label Images URLs	Box Contents URL
```

---

## 📄 .env Format
Create a file called `.env` in the project directory with the following:

```env
OPENAI_API_KEY=your-openai-key-here
SERVICE_ACCOUNT_FILE=ebay-shipping-label-ocr-bb222bb.json  <- That is an example
FOLDER_ID=your-google-drive-folder-id
SPREADSHEET_ID=your-google-sheet-id
SPREADSHEET_URL=https://docs.google.com/spreadsheets/...
```

Make sure to **never upload your `.env` or JSON key to GitHub**.

---

## ▶️ How to Run the App
1. Install Python and Git
2. Clone the repo:
   ```bash
   git clone https://github.com/YourUsername/YourRepo.git "Professor Color Inbound OCR"
   ```
3. Place `.env` and JSON file in the folder
4. Double-click `run.bat`

### What `run.bat` Does:
- Pulls latest code from GitHub
- Opens the Google Sheet in browser
- Sets up the virtual environment in env folder
- Installs dependencies
- Launches the app

---

## 🖥️ User Flow
1. **Start App** — Double-click `run.bat`
2. **Camera Opens** — You’ll see live view + instructions
3. **Press `SPACE`** — Captures single photo (label)
4. **Press `M`** — Activates Multi-Photo Mode
   - Take one label photo → prompt for second
   - Then take box contents photo
5. **App uploads photos** to Drive
6. **Runs OCR using OpenAI**
7. **Populates Google Sheet** with label + tracking + image URLs
8. **Threads** are used so label & content processes don’t block UI

---

## 🧵 Technical Architecture
- **Threading**: `handle_label_phase` and `handle_contents_phase` run in background threads
- **Camera**: Captures at max available resolution, viewport resizes to 1080p
- **Stitching**: Multi-photo labels are vertically combined using OpenCV
- **OCR**: Images encoded as base64 and sent to OpenAI’s Vision API (fine-tuned model)
- **Google Sheets**: Partial row added after label, contents URL appended later
- **Drive**: Images uploaded with public-read permissions and URL stored
- **Environment Vars**: Read via `python-dotenv`

---
## 📅 Label Orientation & Viewport
Ensure the label is right side up when viewed on-screen. We are utilizing a webcam on an arm. The Webcam & Arm will move 
around to ensure that the label is consuming as much of the available viewport as possible. 
- To improve OCR accuracy and user clarity:
- The viewport rotates dynamically using [O] and [P] keys
- Press [O] to rotate counterclockwise, [P] to rotate clockwise
- Adjust the view so the label is upright before capture
- Here is an example of a properly oriented label:
![Correct Label Orientation](./Correct%20Label%20Orientation.png)

This helps the OpenAI model receive consistently formatted input and increases recognition reliability.

---

## 🛠 Troubleshooting
- Camera not opening? Check permissions, try another webcam
- `.env` not loading? Ensure it's in the same folder as `main.py`
- Google errors? Make sure your service account has access to the folder and sheet
- Sheet not updating? Check the headers match exactly as above

---

# 🔁 Ideal User Flow & Error Handling

This app is designed to support a fast and semi-automated workflow — but as with all OCR processes, occasional human verification is critical. Here's the recommended user process and how to handle potential issues:

---

### ✅ Normal Flow

1. **Capture the Label**
   - Place the box in view of the webcam.
   - Press `SPACE` to capture a single label photo, or press `M` to begin **multi-photo mode** for labels that wrap around boxes.
   - The system will capture 1 or 2 images of the label, stitch them if needed, and send them to OpenAI for OCR processing.

2. **Label is Processed**
   - The label image(s) are uploaded to Google Drive.
   - The OpenAI model extracts structured data (sender, recipient, tracking numbers, etc.)
   - A **partial row** is appended to the Google Sheet with this data.

3. **Capture Box Contents**
   - While the label is being processed in the background, the user can begin opening the box.
   - Once opened, press `SPACE` again to take a photo of the **box contents**.
   - This image is uploaded to Drive, and the previously added row is updated with the box contents image URL.

4. **Review the Sheet**
   - After the content image is captured, the Google Sheet should now have:
     - Full shipping label details
     - Image URLs for the label and box contents
   - The user should **compare the row in the sheet with the physical label in hand** before disposing of the box or moving on.

---

### ⚠️ Handling Errors

#### Minor OCR Errors (e.g. a misspelled name or company)

- Manually correct the data in the Google Sheet.
- Highlight the corrected cell with a **light red fill**.
- In **Column P (Remarks)**, add a note describing the error.
  - Example: `OCR misread tracking #` or `Company name cut off`
- These remarks help the developer fine-tune the model with real-world feedback.

#### Major OCR Errors or Blurry Photos

- If the label OCR is **completely incorrect** (e.g. due to poor image quality):
  1. Highlight the **entire row**.
  2. Right-click and select **Delete row** from Google Sheets.
  3. Return to the app and **rescan the label** (you do not need to restart the app).

📌 **Tip:** Always review the Google Sheet label data before cutting open the box. If the scan is invalid, you can easily redo the capture without needing to repack the contents.

---

### 🧠 Best Practices

- **Rotate the viewport (O/P keys)** before capturing so the label appears right-side up.
- Ensure **clear, glare-free, well-lit photos** to minimize OCR mistakes.
- Avoid motion blur: hold the box still for a second before capturing.
- Use a **4K webcam** if possible for better accuracy.
- Always add remarks for issues to help improve the model via future fine-tuning.

---

By following this flow and correcting where needed, you ensure data accuracy and contribute directly to improving the OCR performance over time.


