import React, {useState, useEffect, useRef} from 'react';
import axios from 'axios';
import SpacesView from './../components/spaces_view.js'

function SpacePage() {

//define all constants first
  const [spaceList, setSpacesList] = useState([{}]) 
  const countRef = useRef(0);
  //All the functions here

  const fetchSpaces = async () => {
    axios.get('http://localhost:6656/apiv1/spaces/')
      .then(res => {
        console.log(res.data)
        setSpacesList(res.data)
        countRef.current++;
      })
  }

  useEffect(() => {
    fetchSpaces();
  },[]);

    return (
        <div>
            <h1>Task Manager</h1>
            <h6 className="card text-white bg-primary">FastApi -React</h6>
            <h5 className="card text-white bg-dark">All spaces</h5>
            <div>
            <SpacesView listspace= {spaceList} />
            </div>
            <div>Number of changes to page: {countRef.current}</div>
        </div>
    )
}

export default SpacePage