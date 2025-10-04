import streamlit as st

def zero_sum_game():
    '''
    Function to configure the Zero-Sum game.
    This function will be called when the user selects the Zero-Sum game type.
    The function will include options for setting reward values and additional rules.
    '''
    st.write("Configuring Zero-Sum game...")
    # Add specific configuration or logic for Zero-Sum game
    st.slider("Set the reward value:", min_value=0, max_value=100, value=50)
    st.text_input("Enter additional rules for the Zero-Sum game:")

def prisoners_dilemma_game():
    '''
    Function to configure the Prisoner's Dilemma game.
    This function will be called when the user selects the Prisoner's Dilemma game type.
    The function will include options for setting cooperation rewards and punishment rules.
    '''
    st.write("Configuring Prisoner's Dilemma game...")
    # Add specific configuration or logic for Prisoner's Dilemma game
    st.radio("Choose the cooperation reward:", options=["Low", "Medium", "High"])
    st.text_area("Enter the punishment rules for defection:")