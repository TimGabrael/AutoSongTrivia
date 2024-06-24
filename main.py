import asyncio
import websockets
import json
import requests
from shazamio import Shazam
import aiohttp
from Levenshtein import distance as levenshtein_distance


request_header = {
        "accept": "application/json",
        "accept-language": "en",
        "content-type": "application/json",
        "origin": "https://songtrivia2.io",
        "priority": "u=1, i",
        "referer": "https://songtrivia2.io/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }


def find_all(a_str, sub):
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub)

def get_closest_match(target, options):
    distances = [(option, levenshtein_distance(target, option)) for option in options]
    closest_match = min(distances, key=lambda x: x[1])
    return closest_match


async def download_file(url, save_path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(save_path, 'wb') as f:
                    f.write(await response.read())

async def send_answer(websocket, answer_idx):
    answer = ord("A") + answer_idx
    general_data = bytearray()
    general_data.append(0x0D)
    general_data.append(0xAD)
    general_data += b"PLAYER_ANSWER"
    general_data.append(0x82)
    general_data.append(0xa8)
    general_data += b"answerId"
    general_data.append(0xA1)
    general_data.append(answer)
    general_data.append(0xAB)
    general_data += b"answersType"
    general_data.append(0xA6)
    general_data += b"SINGLE"
    
    return await websocket.send(general_data);

async def send_next_game_step_answer(websocket):
    general_data = bytearray()
    general_data.append(0x0D)
    general_data.append(0xAE)
    general_data += b"NEXT_GAME_STEP"
    general_data.append(0x82)
    general_data.append(0xB2)
    general_data += b"sentDuringGameStep"
    general_data.append(0xAF)
    general_data += b"MANUAL_SOLUTION"
    general_data.append(0xA9)
    general_data += b"timestamp"
    general_data.append(0xCF)
    general_data.append(0x00)
    general_data.append(0x00)
    general_data.append(0x01)
    general_data.append(0x90)
    general_data.append(0x4A)
    general_data.append(0xF1)
    general_data.append(0xBD)
    general_data.append(0xBC)

    return await websocket.send(general_data);

async def send_next_game_step_about(websocket):
    general_data = bytearray()
    general_data.append(0x0D)
    general_data.append(0xAE)
    general_data += b"NEXT_GAME_STEP"
    general_data.append(0x82)
    general_data.append(0xB2)
    general_data += b"sentDuringGameStep"
    general_data.append(0xAE)
    general_data += b"QUESTION_ABOUT"
    general_data.append(0xA9)
    general_data += b"timestamp"
    general_data.append(0xCF)
    general_data.append(0x00)
    general_data.append(0x00)
    general_data.append(0x01)
    general_data.append(0x90)
    general_data.append(0x4A)
    general_data.append(0xF8)
    general_data.append(0xFC)
    general_data.append(0x80)

    return await websocket.send(general_data);

async def send_next_game_step_leaderboard(websocket):
    general_data = bytearray()
    general_data.append(0x0D)
    general_data.append(0xAE)
    general_data += b"NEXT_GAME_STEP"
    general_data.append(0x82)
    general_data.append(0xB2)
    general_data += b"sentDuringGameStep"
    general_data.append(0xB3)
    general_data += b"MANUAL_LEADER_BOARD"
    general_data.append(0xA9)
    general_data += b"timestamp"
    general_data.append(0xCF)
    general_data.append(0x00)
    general_data.append(0x00)
    general_data.append(0x01)
    general_data.append(0x90)
    general_data.append(0x4A)
    general_data.append(0xF8)
    general_data.append(0xFC)
    general_data.append(0x80)

    return await websocket.send(general_data);

async def connect_to_websocket(uri):
    async with websockets.connect(uri) as websocket:
        first_message = True
        answers = []
        answer_idx = -1
        question_counter = 0
        while True:
            message = await websocket.recv()
            if first_message:
                first_response = bytearray()
                first_response.append(0x0A)
                await websocket.send(first_response)
                first_message = False
            else:
                message_str = message.__str__()
                #print(message_str)
                if message_str.find("CURRENT_QUESTION_TRANSLATIONS") != -1:
                    question_counter += 1
                    print("question_counter: ", question_counter)
                    answer_idx = -1
                    answers.clear()
                    all_labels = find_all(message_str, "label")
                    cur_label = ""
                    for label in all_labels:
                        cur_label = ""
                        for i in range(label+4+5, len(message_str)):
                            val = message_str[i]
                            if val != '\\':
                                cur_label += val
                            else:
                                answers.append(cur_label)
                                break

                    for answer in answers:
                        print("answer: ", answer)

                audio_file = message_str.find("https://audio-ssl.itunes.apple.com/itunes-")
                if audio_file != -1 and answer_idx == -1 and len(answers) > 0:
                    file_end = audio_file
                    for i in range(audio_file, len(message_str)):
                        if message_str[i] == '\\':
                            file_end = i
                            break
                    audio_file = message_str[audio_file:file_end]
                    await download_file(audio_file, "temp_file_storage.mpa")
                    shazam = Shazam()
                    audio_info = await shazam.recognize("temp_file_storage.mpa")

                    song_name = audio_info["track"]["title"]
                    artist_name = audio_info["track"]["subtitle"]

                    closest_song = get_closest_match(song_name, answers)
                    closest_artist = get_closest_match(artist_name, answers)
                    answer_idx = 0
                    if closest_song[1] < closest_artist[1]:
                        print(closest_song[0])
                        answer_idx = answers.index(closest_song[0])
                    else:
                        print(closest_artist[0])
                        answer_idx = answers.index(closest_artist[0])
                    print("answer_idx: ", answer_idx)

                presentation = message_str.find("QUESTION\\x80\\xa8QUESTION")
                if presentation == -1:
                    presentation = message_str.find("QUESTION\\x87\\x00\\x80\\xa8QUESTION")
                if presentation != -1 and answer_idx != -1:
                    print("sending_answer: ", answer_idx)
                    await send_answer(websocket, answer_idx)
                
                selected_answer_info = message_str.find("PERSONALIZED_PODIUM")
                if selected_answer_info != -1:
                    await send_next_game_step_answer(websocket)

                question_about_info = message_str.find("QUESTION_ABOUT")
                if question_about_info != -1:
                    await send_next_game_step_about(websocket)

                manual_leader_board_info = message_str.find("MANUAL_LEADER_BOARD")
                if manual_leader_board_info != -1 and question_counter >= 5:
                    print("FINISHED")
                    print("question_count: ", question_counter)
                    await send_next_game_step_leaderboard(websocket)

                refresh_user_data_info = message_str.find("REFRESH_USER_DATA")
                if refresh_user_data_info != -1 and question_counter >= 5:
                    print("REFRESHED USER DATA")
                    last_response = bytearray()
                    last_response.append(0x0C)
                    await websocket.send(last_response)
                    await websocket.close()
                    return


def join_active_game(user_name, uuid, room_id):
    request_data = {
            "avatarUrl": "avatars/1/250.png",
            "countryCode": "02",
            "isSpectator": False,
            "lang": "DE",
            "userName": user_name,
            "uuid": uuid
            }
    r = requests.post(f"https://eu.engine.anthm.io/matchmake/joinById/{room_id}", headers=request_header, json=request_data)
    json_content = json.loads(r.content)
    
    process_id = json_content["room"]["processId"]
    session_id = json_content["sessionId"]
    room_id = json_content["room"]["roomId"]
    
    uri = f"wss://eu.engine.anthm.io/{process_id}/{room_id}?sessionId={session_id}"
    asyncio.get_event_loop().run_until_complete(connect_to_websocket(uri))

def play_alone(user_name, uuid):
    request_data = {
            "avatarUrl": "avatars/5/250.png",
            "categoryName": "Pop",
            "categorySlug": "pop",
            "countryCode": "02",
            "gameType": "SOLO",
            "hasEnergyFee": False,
            "lang": "EN",
            "tenant": "songtrivia",
            "userName": user_name,
            "uuid": uuid
            }
    r = requests.post("https://eu.engine.anthm.io/matchmake/create/kwest_quiz_room", headers=request_header, json=request_data)
    json_content = json.loads(r.content)
    
    process_id = json_content["room"]["processId"]
    session_id = json_content["sessionId"]
    room_id = json_content["room"]["roomId"]
    
    uri = f"wss://eu.engine.anthm.io/{process_id}/{room_id}?sessionId={session_id}"
    asyncio.get_event_loop().run_until_complete(connect_to_websocket(uri))

def play_one_v_one(user_name, uuid):
    request_data = {
            "avatarUrl": "avatars/5/250.png",
            "categorySlug": "pop",
            "countryCode": "02",
            "gameType": "ONE_VERSUS_ONE",
            "hasEnergyFee": False,
            "lang": "EN",
            "tenant": "songtrivia",
            "userName": user_name,
            "uuid": uuid
            }
    r = requests.post("https://eu.engine.anthm.io/matchmake/create/kwest_quiz_room", headers=request_header, json=request_data)
    json_content = json.loads(r.content)
    
    process_id = json_content["room"]["processId"]
    session_id = json_content["sessionId"]
    room_id = json_content["room"]["roomId"]
    
    uri = f"wss://eu.engine.anthm.io/{process_id}/{room_id}?sessionId={session_id}"
    asyncio.get_event_loop().run_until_complete(connect_to_websocket(uri))




play_one_v_one(user_name, uuid)
 
