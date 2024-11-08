import './App.css';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Home from './Components/Home';
import Upload from './Components/Upload';
import Annotate from './Components/Annotate';

function App() {
  return (
    <div className="background-container">
      <div className="top-left">Bird Count</div>
      <div className="top-right">IIITD</div>
      <Router>
        <Routes>
          <Route path='/' element={<Home />} />
          <Route path='/upload' element={<Upload />} />
          <Route path='/annotate' element={<Annotate />} />
        </Routes>
      </Router>
    </div>
  );
}

export default App;