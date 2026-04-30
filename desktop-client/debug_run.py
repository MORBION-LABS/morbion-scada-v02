import sys
import traceback

sys.path.append('c:\\OT_Ops\\SCADA\\morbion-scada-v02\\desktop-client')

def custom_excepthook(exc_type, exc_value, exc_traceback):
    with open('c:\\OT_Ops\\SCADA\\morbion-scada-v02\\desktop-client\\error_trace.txt', 'w') as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = custom_excepthook

import main
main.main()
