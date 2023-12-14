{ pkgs ? import <nixpkgs> {} }:

let
    python = pkgs.python311;
    pypkgs = python.pkgs;
in
pkgs.mkShell rec {
    name = "interview";
    shellHook = ''
        source .bashrc
    '';
    buildInputs = with pkgs; [
        pypkgs.python
        # Loading website html
        chromedriver
        chromium
        pypkgs.selenium
        pypkgs.requests
        # Process website information
        pypkgs.lxml
        pypkgs.tldextract
        pypkgs.fuzzywuzzy
        pypkgs.pandas
        # Testing
        pypkgs.ipython
        pypkgs.nose
    ];
}
