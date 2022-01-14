import React, {useState, useEffect, useRef} from 'react';
import axios from 'axios';
import SpacesView from './../components/spaces_view.js'
import {Button} from 'react-bootstrap';
import { FaPlus} from 'react-icons/fa';
function SpacePage() {

//define all constants first
  const [spaceList, setSpacesList] = useState([{}]) 
  const countRef = useRef(0);
  //All the functions here

  const fetchSpaces = async () => {
    console.log(process.env.REACT_APP_BASE_URL_SERVER);
    axios.get(process.env.REACT_APP_BASE_URL_SERVER+'apiv1/spaces/')
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
            <h5 className="card text-white bg-dark">All spaces</h5>
            <Button variant="danger" style={{width: '100%', marginBottom:'1%'}}><FaPlus></FaPlus> Add Space <FaPlus></FaPlus></Button>
            <div>
            <SpacesView listspace= {spaceList} />
            </div>
            <div>Number of changes to page: {countRef.current}</div>
        </div>
    )
}

export default SpacePage