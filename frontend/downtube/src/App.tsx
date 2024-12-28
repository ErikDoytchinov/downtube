import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import DownloadForm from "./components/DownloadForm";
import ResultPage from "./components/ResultPage";

function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<DownloadForm />} />
                <Route path="/result/:downloadId" element={<ResultPage />} />
            </Routes>
        </Router>
    );
}

export default App;
