import math
import wave
import struct
from datetime import datetime
from pathlib import Path
import sys

def bitconvert(text):
    bits = []
    for char in text:
        b = ord(char) & 0x7F
        for i in range(8):
            bits.append((b >> i) & 1)
    return bits

def preamble():
    bits = []
    preamble_byte = 0xAB
    for _ in range(16):
        for i in range(8):
            bits.append((preamble_byte >> i) & 1)
    return bits

def generateafsk(bits, sample_rate=44100, amplitude=0.5, start_phase=0.0):
    bit_duration = 1.92 / 1000
    samples_per_bit = int(round(sample_rate * bit_duration))
    
    samples = []
    phase = start_phase
    
    f_mark = 2083.3333
    f_space = 1562.5
    
    w_mark = 2.0 * math.pi * f_mark / sample_rate
    w_space = 2.0 * math.pi * f_space / sample_rate
    
    for bit in bits:
        w = w_mark if bit == 1 else w_space
        for _ in range(samples_per_bit):
            samples.append(amplitude * math.sin(phase))
            phase += w
            if phase > 2.0 * math.pi:
                phase -= 2.0 * math.pi
                
    return samples, phase

def generatetone(frequency, duration, sample_rate=44100, amplitude=0.5):
    samples = []
    w = 2.0 * math.pi * frequency / sample_rate
    for i in range(int(sample_rate * duration)):
        samples.append(amplitude * math.sin(w * i))
    return samples

def generatedualtone(f1, f2, duration, sample_rate=44100, amplitude=0.5):
    samples = []
    w1 = 2.0 * math.pi * f1 / sample_rate
    w2 = 2.0 * math.pi * f2 / sample_rate
    for i in range(int(sample_rate * duration)):
        val = (math.sin(w1 * i) + math.sin(w2 * i)) * 0.5 * amplitude
        samples.append(val)
    return samples

def writeaudio(filename, samples, sample_rate=44100):
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        packed_data = []
        for sample in samples:
            val = max(-1.0, min(1.0, sample))
            int_val = int(val * 32767)
            packed_data.append(struct.pack('<h', int_val))
            
        wav_file.writeframes(b''.join(packed_data))

def encodesame(org, eee, locations, purge_time, issue_time, station_id, output_filename="same_message.wav", include_attention=True, attention_type="broadcast"):
    sample_rate = 44100
    all_audio_samples = []
    
    # Format: ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
    # SAME headers are formatted as such, I have tried to follow it to the best of my ability
    loc_string = "".join([f"-{loc}" for loc in locations[:-1]])
    if loc_string:
        loc_string += f"+{locations[-1]}"
    else:
        loc_string = f"-{locations[0]}"
    if len(locations) > 1:
        header_text = f"ZCZC-{org}-{eee}{''.join([f'-{l}' for l in locations[:-1]])}+{locations[-1]}-{purge_time}-{issue_time}-{station_id}-"
    else:
        header_text = f"ZCZC-{org}-{eee}-{locations[0]}+{purge_time}-{issue_time}-{station_id}-"
    print(f"Generated Header Code: {header_text}")

    # Part 1 of the Specific Area Message Encoding EAS Protocol, Preamble and EAS Header Code (aka SAME). I tried my best to implement this, and through my testing it has worked.
    header_bits = preamble() + bitconvert(header_text)
    phase = 0.0
    for i in range(3):
        burst_samples, phase = generateafsk(header_bits, sample_rate=sample_rate, start_phase=phase)
        all_audio_samples.extend(burst_samples)
        if i < 2:
            all_audio_samples.extend([0.0] * sample_rate)
            
    all_audio_samples.extend([0.0] * sample_rate)
    
    # Part 2 of the Specific Area Message Encoding EAS Protocol, attention signal. on wikipedia and the code of federal regulations it is listed to be 853 and 960hz, which I implemented here
    if include_attention:
        print(f"Adding Attention Signal ({attention_type})...")
        if attention_type == "weather":
            attention_samples = generatetone(1050, 8.0, sample_rate=sample_rate)
        else:
            attention_samples = generatedualtone(853, 960, 8.0, sample_rate=sample_rate)

        all_audio_samples.extend(attention_samples)
        all_audio_samples.extend([0.0] * sample_rate)

    # Part 3 of the Specific Area Message Encoding EAS Protocol, audio message. For the sake of having it, I implemented a tone of A4 just so I can technically be to spec
    print("Adding audio message placeholder...")
    message_placeholder = generatetone(440, 2.0, sample_rate=sample_rate, amplitude=0.2)
    all_audio_samples.extend(message_placeholder)
    all_audio_samples.extend([0.0] * sample_rate)  # 1 second pause before tail
    
    # Part 4 of the Specific Area Message Encoding EAS Protocol, the Preamble and EAS EOM code. the EOM code is written as NNNN for some reason so I've gone along with that
    tail_text = "NNNN"
    tail_bits = preamble() + bitconvert(tail_text)
    
    print("Generating Tail/EOM Bursts...")
    phase = 0.0
    for i in range(3):
        burst_samples, phase = generateafsk(tail_bits, sample_rate=sample_rate, start_phase=phase)
        all_audio_samples.extend(burst_samples)
        if i < 2:
            all_audio_samples.extend([0.0] * sample_rate)
            
    # Write everything to file
    print(f"Writing complete waveform to {output_filename}...")
    writeaudio(output_filename, all_audio_samples, sample_rate=sample_rate)
    print("Encoding complete!")

def encodecustom(message, output_filename="same_message.wav", include_attention=True, attention_type="broadcast"):
    sample_rate = 44100
    all_audio_samples = []
    
    # Part 1 of the Specific Area Message Encoding EAS Protocol, Preamble and EAS Header Code (aka SAME). I tried my best to implement this, and through my testing it has worked. In this modification, the EAS Header Code has been replaced with a custom message
    header_bits = preamble() + bitconvert(message)
    
    phase = 0.0
    for i in range(3):
        burst_samples, phase = generateafsk(header_bits, sample_rate=sample_rate, start_phase=phase)
        all_audio_samples.extend(burst_samples)
        if i < 2:
            all_audio_samples.extend([0.0] * sample_rate)

    all_audio_samples.extend([0.0] * sample_rate)

    # Part 2 of the Specific Area Message Encoding EAS Protocol, attention signal. on wikipedia and the code of federal regulations it is listed to be 853 and 960hz, which I implemented here
    if include_attention:
        print(f"Adding Attention Signal ({attention_type})...")
        if attention_type == "weather":
            attention_samples = generatetone(1050, 8.0, sample_rate=sample_rate)
        else:
            attention_samples = generatedualtone(853, 960, 8.0, sample_rate=sample_rate)

        all_audio_samples.extend(attention_samples)
        all_audio_samples.extend([0.0] * sample_rate)

    # Part 3 of the Specific Area Message Encoding EAS Protocol, audio message. For the sake of having it, I implemented a tone of A4 just so I can technically be to spec
    print("Adding audio message placeholder...")
    message_placeholder = generatetone(440, 2.0, sample_rate=sample_rate, amplitude=0.2)
    all_audio_samples.extend(message_placeholder)
    all_audio_samples.extend([0.0] * sample_rate)  # 1 second pause before tail

    # Part 4 of the Specific Area Message Encoding EAS Protocol, the Preamble and EAS EOM code. the EOM code is written as NNNN for some reason so I've gone along with that
    tail_text = "NNNN"
    tail_bits = preamble() + bitconvert(tail_text)

    print("Generating Tail/EOM Bursts...")
    phase = 0.0
    for i in range(3):
        burst_samples, phase = generateafsk(tail_bits, sample_rate=sample_rate, start_phase=phase)
        all_audio_samples.extend(burst_samples)
        if i < 2:
            all_audio_samples.extend([0.0] * sample_rate)

    # Write everything to file
    print(f"Writing complete waveform to {output_filename}...")
    writeaudio(output_filename, all_audio_samples, sample_rate=sample_rate)
    print("Encoding complete!")

# Example Parameters for a Required Weekly Test (RWT)
# ORG = WXR (National Weather Service)
# EEE = RWT (Required Weekly Test)
# Location = 024021 (Example: Montgomery County, Maryland)
# Purge time = 0015 (15 minutes)
# Issue time = 1721200 (Day 172 of the year, 12:00 UTC)
# Station ID = KEC83/NWS (NOAA Weather Radio Station)

length1 = 70

print("=" * length1)
print("LEGAL & SAFETY WARNING")
print("=" * length1)
print("This program is for closed, experimental sandbox environments ONLY.\n")
print("WARNING: Broadcasting EAS tones or SAME data over the air without")
print("proper authorization is a federal crime in most places worldwide.")
print("In the US, violations can incur fines exceeding $10,000")
print("per instance multiplying for repeats, equipment seizure,")
print("and up to 5 years in prison.\n")
print("The author (chiro1879/cheerio/chiroetsn.xyz) assume NO liability for")
print("any misuse, damage, or legal consequences resulting from the use")
print("of this software.\n")
print("Ensure all RF transmitters are OFF, disconnected, assuredly")
print("not able to broadcast the audio this program or any audio player")
print("creates, or is connected exclusively to a dummy load before proceeding.")
print("")
print("=" * length1)
print()
print("To proceed, you must accept all legal risks and responsibilities.")
accept = input("Type 'I understand' to continue, or anything else to exit: ").lower()
if accept == "i understand":
    with open("legalwarningread", "w") as file:
        file.write("User has read and understands the legal warning")
    print("\n")
else:
    print("\nUnderstood, exiting safely.")
    sys.exit(1)

while True:
    question = input("Do you want to send a custom message or a standard EAS? (EAS/Custom) ").lower()
    if question == "eas":
        print("\nAll valid codes can be gotten from this page: https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-11/subpart-B/section-11.31")
        print("Locations can be gotten from the CSV I have bundled alongside the program\n")
        org1 = input("Enter ORG Code (WXR): ") or "WXR"
        eee1 = input("Enter Event Code (RWT): ") or "RWT"
        numbers = []

        while len(numbers) < 32:
            user_input = input("Enter a 6-digit PPSSCC location code (or any non-numeric character to stop): ")

            if not user_input.isdigit():
                break

            if len(user_input) == 6:
                numbers.append(int(user_input))
            else:
                print("not a 6-digit number, not added")

        numbers = numbers or ["000000"]

        purge_time1 = input("Enter a number with the structure HHMM for when the warning is set to expire (e.g 0015 for 15 minutes, default): ") or "0015"
        issue_time1 = input(f"Enter a number with the structure DDDHHMM (for the current time, {datetime.now().strftime("%j%H%M")}, default):") or datetime.now().strftime("%j%H%M")
        station_id1 = input("Enter 8 character long station ID (longer strings will be cut down, can be anything, default testtest): ")[:8].lower() or "testtest"
        outfile = input("Enter filename to output as (same_message.wav): ") or "same_message.wav"
        attention_type1 = input("What attention is required (e.g broadcast (default), weather): ").lower() or "broadcast"
        encodesame(org=org1,
                eee=eee1,
                locations=numbers,
                purge_time=purge_time1,
                issue_time=issue_time1,
                station_id=station_id1,
                output_filename=outfile,
                include_attention=True,
                attention_type=attention_type1
                )
    elif question == "custom":
        print("WARNING: Files and Text can take WAY longer to create, as the system SAME is based on was not meant to deal with this kind of traffic. if you input a large file (even 10kb), expect about a minute or more of wait, a massive wav file (40MB MINIMUM), and a result that will take AGES to load in standard software.")
        question2 = input("File or Text? (F/T) ").lower()
        if question2 == "t":
            inputtext = input("Enter your custom message: ") or "Testing Testing 123"
            outfile = input("Enter filename to output as (same_message.wav): ") or "same_message.wav"
            attention_type1 = input("What attention is required (e.g broadcast (default), weather): ").lower() or "broadcast"
            encodecustom(inputtext,
                        output_filename=outfile,
                        include_attention=True,
                        attention_type=attention_type1
                        )
        elif question2 == "f":
            filepath = input("Enter the filepath: ")
            outfile = input("Enter filename to output as (same_message.wav): ") or "same_message.wav"
            attention_type1 = input("What attention is required (e.g broadcast (default), weather): ").lower() or "broadcast"
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
                encodecustom(content,
                            output_filename=outfile,
                            include_attention=True,
                            attention_type=attention_type1
                            )
    print()

#test1