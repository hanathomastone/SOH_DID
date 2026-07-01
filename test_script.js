// 1. 영상 데이터 데이터셋
const videos = [
    { id: 1, title: "샘플 영상 1 (초식동물)", url: "https://www.w3schools.com/html/mov_bbb.mp4" },
    { id: 2, title: "샘플 영상 2 (곰)", url: "https://www.w3schools.com/html/movie.mp4" },
    { id: 3, title: "샘플 영상 3 (실제 경로 지정용)", url: "path/to/your/local_video.mp4" } 
];

const player = document.getElementById('videoPlayer');
const source = document.getElementById('videoSource');
const playlistContainer = document.getElementById('playlist');
const apiResult = document.getElementById('apiResult');

const BASE_URI = "http://127.0.0.1:5000"

let currentVideoId = videos[0].id;

// 영상 리스트 초기화
function initPlaylist() {
    videos.forEach((video, index) => {
        const item = document.createElement('div');
        item.classList.add('video-item');
        item.innerText = video.title;
        
        if (index === 0) {
            item.classList.add('active');
            source.src = video.url;
            player.load();
            currentVideoId = video.id;
        }

        item.addEventListener('click', () => {
            document.querySelectorAll('.video-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');

            source.src = video.url;
            player.load();
            player.play().catch(error => console.log("자동 재생 막힘 방지:", error));

            currentVideoId = video.id;
        });

        playlistContainer.appendChild(item);
    });
}

// 초기화 실행
initPlaylist();

function showResult(title, data) {
    apiResult.textContent = `${title}\n${JSON.stringify(data, null, 2)}`;
}

async function readResponseJson(response) {
    try {
        return await response.json();
    } catch (error) {
        return {
            state: 'ERROR',
            msg: '서버 응답을 JSON으로 읽지 못했습니다.',
            status: response.status
        };
    }
}

// 공통 요청 함수
async function sendPostRequest(url, data, successMessage, method) {
    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        const result = await readResponseJson(response);

        if (response.ok) {
            alert(`${successMessage} 성공!`);
            console.log('서버 응답:', result);
            showResult(`${successMessage} 성공`, result);
            return result;
        } else {
            const message = result.msg || result.message || `에러 코드: ${response.status}`;
            alert(`${successMessage} 실패 (${message})`);
            console.error('서버 응답:', result);
            showResult(`${successMessage} 실패`, result);
            return null;
        }
    } catch (error) {
        console.error('에러 발생:', error);
        showResult(`${successMessage} 요청 오류`, {
            message: error.message
        });
        alert(`${successMessage} 중 오류가 발생했습니다. (콘솔 확인)`);
        return null;
    }
}

// 1. 사용자에게 토큰 전송 버튼
document.getElementById('postBtn').addEventListener('click', () => {
    const didUri = BASE_URI + "/token/transfer"; 

    // token_name과 DID가 동적으로 변경되어야 하는 부분입니다. 
    let token_name = "TOKEN_" + currentVideoId
    const DID = "did:mitum:minic:0x982d7730abEE1fb6911225E4E74BB43A21Afd7d3fca"

    const didData = {
        "user_DID": DID,
        "token_name" : token_name
    };

    sendPostRequest(didUri, didData, '토큰 전송', 'POST');
});

// 2. 신규 DID 생성 버튼 이벤트
document.getElementById('didBtn').addEventListener('click', () => {
    const didUri = BASE_URI + "/did/create"; 
    const didData = {
    };

    sendPostRequest(didUri, didData, 'DID 생성', 'POST');
});

// 3. 생성된 DID 목록과 DID에 지급된 토큰 개수 출력
document.getElementById('didListBtn').addEventListener('click', async () => {
    const reqUri = BASE_URI + "/did/dids";

    try {
        const response = await fetch(reqUri);
        const result = await readResponseJson(response);

        if (response.ok) {
            console.log('DID 목록:', result);
            showResult('DID 목록', result);
        } else {
            console.error('DID 목록 조회 실패:', result);
            showResult('DID 목록 조회 실패', result);
            alert(`DID 목록 조회 실패 (에러 코드: ${response.status})`);
        }
    } catch (error) {
        console.error('에러 발생:', error);
        showResult('DID 목록 요청 오류', {
            message: error.message
        });
        alert('DID 목록 조회 중 오류가 발생했습니다. (콘솔 확인)');
    }
});

