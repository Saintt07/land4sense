# Land4Sense

## Project Description

**Land4Sense** is a landslide analysis and monitoring system that uses satellite imagery and machine-learning models to identify areas that may be affected by landslides. It processes satellite data and presents the analysis results through an interactive map, allowing users to view landslide-affected areas, their classifications, and other relevant information.

The system combines Random Forest (RF) and U-Net model outputs with pixel-based classification to identify and display landslide-prone areas.

## Features

### Frontend

- **Interactive Landslide Map** – Displays landslide analysis results through an interactive map.
- **Satellite Map Tiles** – Uses locally stored satellite tile images as the map background.
- **GeoJSON Visualization** – Displays landslide polygons and their corresponding information.
- **Color-Coded Risk Classification** – Displays Low, Moderate, and High classifications using different polygon colors.
- **Map Overlay Controls** – Allows users to adjust the visibility and opacity of the landslide overlay.
- **Feature Details** – Displays information such as affected area, landslide pixel count, patch coverage, Random Forest confidence, Random Forest pixel count, and coordinates.
- **Map Navigation** – Allows users to explore and navigate the map.

### Backend

- **Satellite Data Processing** – Processes prepared satellite-image patches for landslide analysis.
- **Machine-Learning Analysis** – Uses Random Forest and U-Net models as part of the analysis workflow.
- **Pixel-Based Classification** – Classifies analyzed areas according to the number of landslide pixels:
  - **Low:** 0–14 pixels
  - **Moderate:** 15–150 pixels
  - **High:** 151 pixels or more
- **User Authentication** – Supports account registration and login using JWT-based authentication.
- **Protected Prediction Endpoint** – Requires authentication before a prediction request can be submitted.
- **Prediction Validation** – Checks uploaded data for valid format, dimensions, file size, and other input requirements.

## Project Structure

The project is divided into two main components: the frontend and backend.

```text
land4sense/
├── backend/
│   ├── ...
│   └── ...
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── tiles/
│       └── [zoom level]/
│           └── [x]/
│               └── [y].png
└── README.md
```

*Note: The CSS and JavaScript filenames above are examples. Replace them with the actual filenames used in the frontend.*

## Installation and Setup

### Requirements

- Git
- Python 3
- MySQL Server
- A modern web browser
- Backend dependencies listed in the repository
- Trained machine-learning model files required for prediction

### 1. Clone the Repository

```bash
git clone https://github.com/Saintt07/land4sense.git
cd land4sense
```

### 2. Frontend Setup

The frontend uses HTML, CSS, and JavaScript, with locally stored map tile images.

1. Open a terminal inside the `frontend` directory.
2. Start a local web server:

```bash
python -m http.server 5500
```

3. Open the application in your browser:

```text
http://localhost:5500/
```

Keep the `tiles` folder in its expected location so the map can load the local satellite imagery.

**Note:** An internet connection may still be required if the frontend loads external libraries or map resources through a CDN.

### 3. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment.

**Windows:**

```powershell
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

Install the required dependencies using the backend's dependency file. If it is named `requirements.txt`, run:

```bash
pip install -r requirements.txt
```

### 4. Database Configuration

1. Start MySQL Server.
2. Create a database named `landslide4sense`.
3. Run the database setup scripts in the following order:
   - `01_schema`
   - `02_seed`
   - `03_app_user`
   - `04_auth`
4. Configure the backend environment variables to match your MySQL connection.

### 5. Environment Configuration

Create a `.env` file inside the backend directory and provide the required database credentials and JWT secret.

Use your own database credentials and a strong, unique JWT secret.

**Do not upload `.env` files, passwords, or secret keys to GitHub.**

### 6. Machine-Learning Model Setup

Place the required trained Random Forest and U-Net model files in the locations expected by the backend.

Prediction functionality will not work if the required model files are missing.

### 7. Run the Backend

With the virtual environment activated, start the FastAPI application using its configured entry point.

For example, if the application entry point is `main.py` and the FastAPI instance is named `app`:

```bash
uvicorn main:app --reload
```

The API documentation can be accessed at:

```text
http://127.0.0.1:8000/docs
```

### 8. Run the Frontend and Backend Together

Keep both the frontend and backend servers running in separate terminals.

- Frontend: `http://localhost:5500/`
- Backend: `http://127.0.0.1:8000/`

Ensure that the frontend's API configuration points to the correct backend address if it communicates with the backend.

## Prediction Input Requirements

The backend prediction endpoint expects a prepared HDF5 (`.h5`) file rather than a raw GeoTIFF (`.tif`) satellite image.

The input must meet the following requirements:

- Contain a dataset named `img`.
- Have an exact shape of `(128, 128, 14)`.
- Be no larger than 5 MB.
- Contain finite numeric values.
- Pass the backend's cloud-data validation.

Prediction requests also require a valid authenticated session.

## Risk Classification Reference

| Classification | Landslide Pixel Count | Map Color |
|---|---:|---|
| Low | 0–14 | Green (`#2ECC71`) |
| Moderate | 15–150 | Orange (`#F39C12`) |
| High | 151 or more | Red (`#E74C3C`) |

Classification follows the project's current pixel-count rules. The current implementation also includes a Metro Manila exception that assigns the Low classification.

## Data and Model Files

The frontend requires its local tile images to display the satellite map background. These are separate from the original satellite TIFF files used during data preparation.

Large TIFF datasets, trained model files, and other supporting data should only be included in the repository if they are necessary for the application to run and are appropriate to distribute.

If certain datasets or model files are not included, provide instructions on how users can obtain or configure them separately.
