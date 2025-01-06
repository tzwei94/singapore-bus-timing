## Setup

1. Start venv
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Rename the `.env.example` file to `.env` in the project root

4. Replace `your_lta_api_key` with your LTA DataMall API key, and `your_first_bus_stop_code` and `your_second_bus_stop_code` with the desired bus stop codes.
   ```
   API_KEY=your_lta_api_key //Get this from LTA DataMall
   BUS_STOP_CODE_A=your_first_bus_stop_code
   BUS_STOP_CODE_B=your_second_bus_stop_code
   ```

## Usage
Strat venv: 
```
source .venv/bin/activate
```

Run the main script: 
```
python app/main.py
```
