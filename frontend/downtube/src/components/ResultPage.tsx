import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

function ResultPage() {
    const { downloadId } = useParams();
    const [status, setStatus] = useState("loading");
    const [downloadType, setDownloadType] = useState("");

    useEffect(() => {
        const eventSource = new EventSource(`/api/status/${downloadId}`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setStatus(data.status);
                setDownloadType(data.download_type);

                if (data.status === "completed" || data.status === "error") {
                    eventSource.close();
                }
            } catch (error) {
                console.error("Failed to parse SSE data:", error);
            }
        };

        eventSource.onerror = (error) => {
            console.error("SSE error:", error);
            eventSource.close();
        };

        return () => {
            eventSource.close();
        };
    }, [downloadId]);

    return (
        <div className="container mx-auto px-4 py-12">
            <h1 className="text-4xl font-bold text-center text-gray-800 mb-8">
                Downtube
            </h1>
            <div className="max-w-md mx-auto bg-white p-8 rounded shadow">
                {status === "loading" && (
                    <p className="text-center text-gray-700 mb-6">
                        Checking download status...
                    </p>
                )}
                {status === "downloading" && (
                    <p className="text-center text-gray-700 mb-6">
                        Your file is being processed. Please wait...
                    </p>
                )}
                {status === "completed" && (
                    <>
                        <p className="text-center text-gray-700 mb-6">
                            Your file is ready for download.
                        </p>
                        <a
                            href={`/api/download_video/${downloadId}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block text-center bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded"
                        >
                            Download{" "}
                            {downloadType === "audio" ? "Audio" : "Video"}
                        </a>
                    </>
                )}
                {status === "too-large" && (
                    <p className="text-center text-gray-700 mb-6">
                        The file is too large to download.
                    </p>
                )}
                {status === "deleted" && (
                    <p className="text-center text-gray-700 mb-6">
                        This download has expired.
                    </p>
                )}
                {status === "error" && (
                    <p className="text-center text-gray-700 mb-6">
                        An error occurred while processing the download.
                    </p>
                )}

                <a
                    href="/"
                    className="block text-center bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded mt-4"
                >
                    Download Another
                </a>
            </div>
        </div>
    );
}

export default ResultPage;
