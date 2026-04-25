Team members:

Gabriella Hawkes - geh0042@auburn.edu

Reid Finley Roberts - rfr0012@auburn.edu

Artemis Dolihite - rzd0070@auburn.edu


AI Model
google/gemma-3-1b-it

IT IS REQUIRED TO DOWNLOAD THE REPO FOR FILE ORGANIZATION PURPOSES
PLEASE USE THE SOURCE PDF'S AS STORED IN THE REPO AS THE INPUTS

The binary is located in the dist folder

When running the file, it requires the file paths 
to the two requirement documents as extra arguments to the function.
E.G ./dist/run_full_project file/path/to/cis-r1.pdf file/path/cis-r3.pdf

Also, if you run into issues with Hugging Face logins in your environment,
 try uncommenting line 10 of Extractor.py,
 #login(token=os.environ["HF_TOKEN"])
 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If attempting to run the pieces of the project separately,
    Please take care to uncomment the block of code at the
    start of the extractor() function pertaining to inputs,
    as well as the file strings just below it.