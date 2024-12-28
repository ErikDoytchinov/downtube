import React, { useState } from "react";

function DownloadForm() {
    const [videoUrl, setVideoUrl] = useState("");

    const handleSubmit = async (
        event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
        downloadType: string
    ) => {
        event.preventDefault();
        if (!videoUrl) {
            alert("Please enter a video URL!");
            return;
        }

        // POST to API endpoint
        try {
            const response = await fetch("/api/download", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    video_url: videoUrl,
                    download_type: downloadType,
                }),
            });

            console.log(response);

            if (!response.ok) {
                throw new Error("Failed to submit download request.");
            }

            const data = await response.json();
            window.location.href = `/result/${data.download_id}`;
        } catch (error) {
            console.error("Error submitting download request:", error);
            alert("An error occurred. Please try again.");
        }
    };

    return (
        <div className="bg-slate-900 h-lvh">
            <div className="container mx-auto px-4 py-12 ">
                <h1 className="text-4xl font-bold text-center text-slate-200 mb-8">
                    Downtube
                </h1>
                <p className="text-center text-slate-200 mb-12">
                    Download YouTube videos instantly by entering the video link
                    below.
                </p>
                <div className="max-w-md mx-auto bg-white p-8 rounded shadow">
                    <form className="space-y-4">
                        <label className="block">
                            <input
                                type="url"
                                required
                                className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
                                placeholder="Enter the YouTube video URL"
                                value={videoUrl}
                                onChange={(e) => setVideoUrl(e.target.value)}
                            />
                        </label>
                        <div className="flex space-x-2">
                            <button
                                type="button"
                                onClick={(e) => handleSubmit(e, "video")}
                                className="flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded text-center"
                            >
                                Download Video
                            </button>
                            <button
                                type="button"
                                onClick={(e) => handleSubmit(e, "audio")}
                                className="flex-1 bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded text-center"
                            >
                                Download Audio
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}

export default DownloadForm;
