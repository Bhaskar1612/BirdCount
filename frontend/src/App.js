import './App.css';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Home from './Components/Home';
import Upload from './Components/Upload';

function App() {
  return (
    <div className="background-container">
    <Router>
      <Routes >
        <Route path='/' element={<Home/>} />
        <Route path='/upload' element={<Upload/>}/>
      </Routes>
    </Router>
    </div>
  );
}
export default App;
