from flask import Flask, jsonify, send_file, request, Response
from flask_cors import CORS
import os, re, locale, urllib

locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

app = Flask(__name__)
CORS(app, expose_headers="Content-Disposition")

upload_dir = "./uploads"
temp_dir = "./temp"

if not os.path.exists(upload_dir):
    os.makedirs(upload_dir)

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)


def sanitize_filename(filename):
    # Remove leading/trailing whitespaces
    filename = filename.strip()

    # Replace consecutive whitespaces with a single whitespace
    filename = re.sub(r"\s+", " ", filename)

    # Remove illegal characters except for whitespaces and periods
    filename = re.sub(r"[^\w\s.-]", "", filename)

    return filename


def get_filenames_in_subfolder(subfolder_path):
    filenames = os.listdir(subfolder_path)
    file_info_list = []

    for filename in filenames:
        file_path = os.path.join(subfolder_path, filename)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            file_info = {"filename": filename, "file_size": file_size}
            file_info_list.append(file_info)

    return file_info_list


def combine_chunks(filename, total_chunks):
    with open(f"{upload_dir}/{filename}", "wb") as outfile:
        for chunk_id in range(total_chunks):
            with open(f"{temp_dir}/{filename}.{chunk_id}", "rb") as infile:
                outfile.write(infile.read())
            # Remove the individual chunk file after combining
            os.remove(f"{temp_dir}/{filename}.{chunk_id}")


@app.route("/status", methods=["GET"])
def get_status():
    return jsonify(status="ONLINE")


@app.route("/get_file_info_list", methods=["GET"])
def get_file_info_list():
    file_info_list = get_filenames_in_subfolder(upload_dir)
    return jsonify(file_info_list)


# @app.route("/get_filenames", methods=["GET"])
# def get_filenames():
#     file_info_list = get_filenames_in_subfolder(upload_dir)
#     return jsonify(file_info_list)


def parse_range_header(range_header, file_size):
    range_units, range_value = range_header.strip().split("=")
    start, end = range_value.split("-")

    if start:
        start = int(start)
    else:
        start = 0

    if end:
        end = int(end)
    else:
        end = file_size - 1

    return start, end


@app.route("/download_file/<path:filename>", methods=["GET"])
def download_file(filename):
    decoded_filename = urllib.parse.unquote(filename)

    file_path = f"./uploads/{decoded_filename}"
    file_size = os.path.getsize(file_path)

    range_header = request.headers.get("Range")
    if range_header:
        start, end = parse_range_header(range_header, file_size)
        chunk_size = end - start + 1

        with open(file_path, "rb") as file:
            file.seek(start)
            data = file.read(chunk_size)

        return Response(
            data,
            206,  # Partial Content
            mimetype="application/octet-stream",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    # If no range header present, send the entire file
    return send_file(file_path)


# @app.route("/download_file/<path:filename>", methods=["GET"])
# def download_file(filename):
#     decoded_filename = urllib.parse.unquote(filename)
#     return send_file(f"./uploads/{decoded_filename}")


@app.route("/upload_file", methods=["POST"])
def upload_file():
    chunk = request.files["chunk"]
    chunk_id = int(request.form["chunkId"])
    total_chunks = int(request.form["totalChunks"])

    if os.path.exists(f"{temp_dir}/{chunk.filename}"):
        os.remove(f"{temp_dir}/{chunk.filename}")

    chunk.save(f"{temp_dir}/{chunk.filename}.{chunk_id}")

    saved_chunks = os.listdir(temp_dir)
    received_chunk_size = 0
    for saved_chunk in saved_chunks:
        if saved_chunk.startswith(chunk.filename):
            received_chunk_size += 1

    print(f"{received_chunk_size}. chunck received of total {total_chunks}")
    if received_chunk_size == total_chunks:
        combine_chunks(chunk.filename, total_chunks)
        return {
            "data": {"type": "file", "name": chunk.filename},
            "message": "File uploaded successfully.",
            "success": True,
        }

    return {
        "data": {"type": "chunk", "name": str(chunk_id)},
        "message": f"Chunk uploaded successfully. ({received_chunk_size} / {total_chunks})",
        "success": True,
    }


@app.errorhandler(Exception)
def handle_exception(error):
    print(error)
    return {
        "data": None,
        "message": f"{error}",
        "success": False,
    }, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
