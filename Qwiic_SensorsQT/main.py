import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    # Create the QApplication instance
    app = QApplication(sys.argv)
    
    #app.setFont(QFont("Inter", 10))
    #matplotlib.use('Qt5Agg') 
    
    # Initialize the main window
    window = MainWindow()
    
    # Show the main window
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec_())
