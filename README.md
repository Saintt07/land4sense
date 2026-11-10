# Land4Sense

## Project Description

**Landslide4Sense** is a landslide analysis and monitoring system that uses satellite imagery and machine-learning models to identify areas that may be affected by landslides. It processes satellite data and presents the analysis results through an interactive map, allowing users to view landslide-affected areas and their classifications.

The system uses Random Forest (RF) and U-Net models as part of its landslide analysis workflow.

## Features

### Frontend

- **Interactive Landslide Map** – Displays landslide analysis results through an interactive map.
- **Satellite Map Tiles** – Uses locally stored satellite tile images as the map background.
- **GeoJSON Visualization** – Displays landslide polygons and their corresponding information.
- **Color-Coded Classification** – Uses different colors to represent Low, Moderate, and High classifications.
- **Map Overlay Controls** – Allows users to adjust the visibility and opacity of map overlays.
- **Feature Details** – Displays information about selected map features.

### Backend

- **Satellite Data Processing** – Processes prepared satellite-image patches for landslide analysis.
- **Machine-Learning Analysis** – Uses Random Forest and U-Net models.
- **Pixel-Based Classification** – Classifies analyzed areas according to the number of landslide pixels.
- **User Authentication** – Supports account registration and login using JWT-based authentication.
- **Protected Prediction Endpoint** – Requires authentication before a prediction request can be submitted.
- **Prediction Validation** – Checks uploaded data for valid format, dimensions, file size, and other input requirements.

## Project Structure

The project is divided into two main components: the frontend and backend.

```text
land4sense/
├── backend/
│   ├── app/
│   ├── models/
│   │   ├── channel_mean.npy
│   │   ├── channel_std.npy
│   │   ├── rf_landslide_model.joblib
│   │   └── unet_landslide.pth
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

*Note: The frontend filenames shown above are examples. Refer to the actual filenames in the repository.*

## Installation and Setup

### Requirements

- Git
- Python 3
- MySQL Server
- A modern web browser
- Backend dependencies listed in `requirements.txt`
- Required machine-learning model files

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

**Note:** An internet connection may still be required if the frontend uses external libraries or resources through a CDN.

### 3. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the environment.

**Windows:**

```powershell
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 4. Database Configuration

1. Start MySQL Server.
2. Create a database named `landslide4sense`.
3. Run the database setup scripts in the following order:

   1. `01_schema`
   2. `02_seed`
   3. `03_app_user`
   4. `04_auth`

4. Configure the backend environment variables to match your MySQL connection.

### 5. Environment Configuration

Create a `.env` file inside the `backend` directory and provide the required database credentials and JWT secret.

Use your own database credentials and generate a strong, unique JWT secret.

**Security reminders:**

- Do not upload `.env` files to GitHub.
- Do not expose database passwords or JWT secret keys.
- Keep sensitive configuration values private.

### 6. Machine-Learning Model Setup

The backend requires the following four files inside the `backend/models/` directory:

| File | Purpose |
|---|---|
| `rf_landslide_model.joblib` | Random Forest model |
| `unet_landslide.pth` | U-Net model |
| `channel_mean.npy` | Normalization channel means |
| `channel_std.npy` | Normalization channel standard deviations |

The Random Forest model is approximately **3.27 GB**, so it is stored separately from this GitHub repository.

**Download the model files here:**

[Land4Sense Model Files – Google Drive](https://drive.google.com/drive/folders/18dfv2lJCHfQifw4Xpa5YJmKRctIx5VZv)

After downloading, place the files inside `backend/models/`.

The folder should look like this:

```text
backend/
└── models/
    ├── rf_landslide_model.joblib
    ├── unet_landslide.pth
    ├── channel_mean.npy
    └── channel_std.npy
```

Make sure all four files are present before running the prediction endpoint. Keep their filenames unchanged.

**Important:** The Random Forest model is not included in GitHub because it exceeds GitHub's regular file size limit. Download it separately using the Google Drive link above.

### 7. Run the Backend

Make sure your virtual environment is activated and your terminal is inside the `backend` directory.

Run the following command:

```bash
uvicorn app.main:app --reload
```

The backend API will be available at:

```text
http://127.0.0.1:8000/
```

To access the interactive API documentation, open:

```text
http://127.0.0.1:8000/docs
```

The Swagger documentation allows you to view and test the available API endpoints.

### 8. Run the Frontend and Backend Together

Keep the frontend and backend servers running in separate terminals.

- **Frontend:** `http://localhost:5500/`
- **Backend:** `http://127.0.0.1:8000/`

If the frontend communicates with the backend API, make sure its API configuration points to the correct backend address.

## Prediction Input Requirements

The backend prediction endpoint expects a prepared HDF5 (`.h5`) file rather than a raw GeoTIFF (`.tif`) satellite image.

The input file must meet the following requirements:

- Contain a dataset named `img`.
- Have an exact shape of `(128, 128, 14)`.
- Be no larger than 5 MB.
- Contain finite numeric values.
- Pass the backend's cloud-data validation.

Prediction requests also require a valid authenticated session.

## Risk Classification Reference

The system uses the following pixel-count thresholds for classification:

| Classification | Landslide Pixel Count | Map Color |
|---|---:|---|
| Low | 0–14 | Green (`#2ECC71`) |
| Moderate | 15–150 | Orange (`#F39C12`) |
| High | 151 or more | Red (`#E74C3C`) |

The current implementation also includes a Metro Manila exception that assigns the Low classification.

## Data and Model Files

The frontend requires its local tile images to display the satellite map background. These files are separate from the original satellite TIFF files used during data preparation.

Large satellite TIFF datasets and the Random Forest model are stored separately from the Git repository.

Refer to the [Machine-Learning Model Setup](#6-machine-learning-model-setup) section for instructions on downloading the required model files.

## How to Run the Frontend

1. Make sure Python 3 is installed on your computer.
2. Open Command Prompt or PowerShell.
3. Navigate to the frontend directory:

```bash
cd frontend
```

4. Start the local development server:

```bash
python -m http.server 5500
```

5. Open your browser and visit:

```text
http://localhost:5500/
```

6. The Land4Sense frontend should now be accessible through your browser.

**Notes:**

- Keep the terminal running while using the frontend.
- Make sure the `tiles` folder remains in its expected location.
- An internet connection may be required if the frontend uses external libraries or map resources through a CDN.
- If the frontend communicates with the backend API, make sure the backend is running and the API address is correctly configured.
