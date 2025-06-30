import React from "react";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import { Helmet, HelmetProvider } from "react-helmet-async";
import ProtectedRoute from "./Common/ProtectedRoute";
import Login from "./Common/Login";
import Signup from "./Common/SignUp";
import HomePage from "./HomePage";
import LandingPage from "./ObjectDetection/components/LandingPage";
import ActiveLearning from "./ObjectDetection/components/ActiveLearning";
import Upload from "./BirdCount/Upload";
import Annotate from "./BirdCount/Annotate";
import Gallery from "./BirdCount/Gallery";
import RidLandingPage from "./ReID/components/LandingPage";
import RidCollage from "./ReID/components/Collage";
import AdminDashboard from "./Common/AdminDashboard";
import RegionView from "./BirdCount/RegionView";
import ActiveLearningBirdcount from "./BirdCount/ActiveLearningBirdcount";
import { ActiveLearningBirdcountDetail } from "./BirdCount/ActiveLearningDetail";

function App() {
  return (
    <HelmetProvider>
      <Router
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Routes>
                  <Route
                    path="/"
                    element={
                      <>
                        <Helmet>
                          <title>Wildlife Monitoring Systems</title>
                        </Helmet>
                        <HomePage />
                      </>
                    }
                  />
                  <Route
                    path="/species-segregation"
                    element={
                      <>
                        <Helmet>
                          <title>Species Segregation</title>
                        </Helmet>
                        <LandingPage />
                      </>
                    }
                  />
                  <Route
                    path="/active-learning"
                    element={
                      <>
                        <Helmet>
                          <title>Active Learning</title>
                        </Helmet>
                        <ActiveLearning />
                      </>
                    }
                  />
                  <Route path="/upload" element={<Upload />} />
                  <Route path="/annotate" element={<Annotate />} />
                  <Route path="/gallery" element={<Gallery />} />
                  <Route path="/region-view" element={<RegionView/>}/>
                  <Route path="/active-learning-birdcount" element={<ActiveLearningBirdcount/>}/>
                  <Route path="/active-learning-birdcount/detail" element={<ActiveLearningBirdcountDetail/>}/>
                  <Route
                    path="/re-identification-landing-page"
                    element={<RidLandingPage />}
                  />
                  <Route path="/reid/collage" element={<RidCollage />} />
                  <Route path="/admin" element={<AdminDashboard />} />
                  {/* <Route path="/gallery" element={<Gallery />} /> */}
                </Routes>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>
    </HelmetProvider>
  );
}

export default App;
