# Ultimate Image Converter (Web)

## Overview

The Ultimate Image Converter is a web-based application that allows users to convert images between different formats (PNG, JPEG, WEBP, GIF, BMP, TIFF) and resize them. The application provides a simple drag-and-drop interface for uploading multiple images and processes them server-side using Python's PIL library. Users can adjust quality settings and choose from different resize modes including percentage scaling and exact dimensions.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Single Page Application**: Uses vanilla HTML, CSS, and JavaScript without any frontend frameworks
- **File Upload Interface**: Implements drag-and-drop functionality with a file input element that accepts multiple image files
- **Form-based Configuration**: Provides controls for format selection, quality adjustment, and resize options through HTML form elements
- **Responsive Design**: Uses CSS flexbox for layout with a card-based design that adapts to different screen sizes

### Backend Architecture
- **Flask Web Framework**: Lightweight Python web server handling HTTP requests and file processing
- **RESTful API Design**: Single `/api/convert` endpoint that accepts POST requests with multipart form data
- **Image Processing Pipeline**: Uses PIL (Python Imaging Library) for format conversion, EXIF orientation correction, and resizing operations
- **File Handling**: Processes uploaded files in memory without persistent storage, returning converted images as downloads

### Request Processing Flow
- **Input Validation**: Checks for file presence and validates target format against allowed formats
- **Quality Parameter Handling**: Implements format-specific quality settings (JPEG/WEBP use quality, PNG uses compression levels)
- **Batch Processing**: Supports multiple file uploads with individual processing for each image
- **Response Format**: Returns either single files or ZIP archives depending on the number of processed images

### Error Handling Strategy
- **Input Validation**: Returns JSON error responses for missing files or unsupported formats
- **Format Support**: Maintains a whitelist of supported image formats with their MIME types and file extensions
- **Quality Bounds**: Enforces quality parameter limits (1-100) with automatic clamping

## External Dependencies

### Core Python Libraries
- **Flask**: Web framework for handling HTTP requests and routing
- **PIL (Pillow)**: Image processing library for format conversion, resizing, and EXIF handling
- **zipfile**: Standard library for creating ZIP archives when multiple files are processed

### Browser APIs
- **File API**: For handling drag-and-drop file uploads and multi-file selection
- **FormData API**: For constructing multipart form requests to the backend
- **Fetch API**: For making asynchronous HTTP requests to the conversion endpoint

### Image Format Support
- **Supported Formats**: PNG, JPEG, WEBP, GIF, BMP, TIFF with format-specific optimization parameters
- **EXIF Handling**: Automatic orientation correction using PIL's ImageOps.exif_transpose