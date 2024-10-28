import React from 'react';
import { Link } from 'react-router-dom';
import './Home.css'; 

function Home() {
  return (
    <div>
      <header className="title">Bird Count</header>
    <div className='home-cont'>
        <Link to="/admin" className="role-link">Account</Link>
        <Link to="/upload" className="role-link">Bird Count</Link>
      </div>
    </div>
  );
}

export default Home;