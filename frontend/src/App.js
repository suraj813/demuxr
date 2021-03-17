import React, { useState, useEffect } from 'react'
import ReactPlayer from 'react-player/file'
import { styled } from "@material-ui/core/styles";
import { spacing } from "@material-ui/system";
import MuiButton from "@material-ui/core/Button";
import { LinearProgress, IconButton, Typography, Slider, CircularProgress } from '@material-ui/core';
import PauseCircleFilledIcon from '@material-ui/icons/PauseCircleFilled';
import PlayCircleFilledIcon from '@material-ui/icons/PlayCircleFilled';
import './App.css'
import AudioWave from "./audiowave"

const API_BASE_URL = '/api/'
// const API_BASE_URL = 'http://localhost:5000/api/'
const Button = styled(MuiButton)(spacing)

function App() {
  const [url, setURL] = useState('');
  const [urlData, setUrlData] = useState({});
  const [demuxComplete, setDemuxComplete] = useState(false);
  const [inferHTTP, setInferHTTP] = useState(0);
  // const [inferMsg, setInferMsg] = useState('');

  function getURLInfo(url) {
    setURL(url);
    console.log('url set to ', url)
    var info_api_str = API_BASE_URL+ "info?url=" + url;
    if (url !== '') {
      fetch(info_api_str)
        .then(response => response.json())
        .then(data => {
          setUrlData(data);
        })
        .catch(error => console.error(error));
    }
    return true;
  }

  function runInference() {
    if (!urlData) getURLInfo(url);
    
    console.log('running inference for url', url);
    var infer_api_str = API_BASE_URL + "demux?url=" + url;
    setDemuxComplete(false);

    fetch(infer_api_str)
      .then(res => res.json())
      .then(data => {
        // setInferMsg(data['msg']);
        setInferHTTP(data['status']);
        setDemuxComplete(true);
        console.log("inferMsg: ", inferMsg);
        console.log("inferHTTP: ", inferHTTP);})
      .catch(error => { 
        console.error(error);
        setDemuxComplete(false);
      });
  }

  return (
    <div className='App'>
      <div className="wrapper">
        <UserInput getURLInfo={getURLInfo} runInference={runInference} />
        {/* <Player folder={urlData['folder']} demuxComplete={demuxComplete} />  */}
        <Player folder="http://demucs-app-cache.s3.amazonaws.com/0UHwkfhwjsk" demuxComplete={false} /> 
        
        <aside className="sidebar">Sidebar</aside>
        <footer className="footer">Made with &#127927; by @subramen</footer>
      </div>
    </div>
  );
}


function UserInput({ getURLInfo, runInference}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    setTimeout(runInference, 1000);
  };

  return (
    <div className="user-input">
      <Typography className="prompt" variant="h2" align="left">Ready to play?</Typography>
        <input type="text" className="search-bar" placeholder="Paste URL here" 
        onChange={(e) => { getURLInfo(e.target.value) }}/>
        <span className="btn-progress">
          <Button onClick={handleSubmit} px="45px" variant="contained" color="primary">Go</Button>
        </span>
    </div>
  );
}
    

function Player({folder, demuxComplete}) {
  const stems = ['original', 'bass', 'drums', 'other', 'vocals'];
  const [playing, setPlaying] = useState(false);
  const [readyCount, setReadyCount] = useState(0);
  
  const handleReady = () => {
    setReadyCount(readyCount + 1);
    if (readyCount === stems.length) {
      console.log('ready to play!')
    }
  };

  return (
    <div className='player'>
      <Stem playing={playing} folder={folder} stem='original' onReady={handleReady} demuxComplete={demuxComplete} />
      <div className='stemgroup'>
        {demuxComplete ? 
        stems.map(stem => 
          <Stem folder={folder} stem={stem} playing={playing} onReady={handleReady} demuxComplete={demuxComplete}/>)
        : null}
      </div>
      <div className='play-btn'>
        <PlayPauseButton 
          onClick={() => {setPlaying(!playing)}} 
          playing={playing} 
          disabled={readyCount < stems.length}> 
          Play/Pause 
        </PlayPauseButton>
      </div>
    </div>
  );
}


function Stem(props) {
  const {folder, stem, playing, onReady, demuxComplete} = props;
  const [volume, setVolume] = useState(0.8);
  const url = folder + '/' + stem + '.mp3';

  return (
    <div className={'stem ' + stem}>
      <Typography id="label" align="center">{stem}</Typography>
      <AudioWave
        url={url}
        volume={volume}
        playing={playing}
        onReady={onReady}
        demuxComplete={demuxComplete}
      />
      <div className='stem-slider'>
        <Slider
          min={0} max={1}
          step={0.01}
          value={volume}
          onChange={(e,v) => setVolume(v)}
          color="primary"
          aria-labelledby="label"
        />
      </div>
    </div>
  );
}

function PlayPauseButton(props) {
  const {onClick, playing, disabled} = props;
  const play_pause = playing ?  <PauseCircleFilledIcon fontSize="inherit"/> : <PlayCircleFilledIcon fontSize="inherit"/>
  return (
    <IconButton color="primary" aria-label="play/pause" onClick={onClick} disabled={disabled}>
      {play_pause}
    </IconButton>
  );
}






export default App;
