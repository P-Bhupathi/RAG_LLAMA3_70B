from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings 
from pymongo import MongoClient, WriteConcern
from pymongo.errors import *
from django.contrib.auth import logout
from rest_framework.decorators import api_view
from rest_framework.response import Response
import os
import shutil
import json
from bson import ObjectId

from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt

#----------------------------------------------------------
from langchain_groq import ChatGroq
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain.chains import create_retrieval_chain
# from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, UnstructuredPDFLoader
from langchain_community.document_loaders.word_document import UnstructuredWordDocumentLoader, Docx2txtLoader
from dotenv import load_dotenv
#----------------------------------------------------------

MONGO_URI = settings.MONGO_URI
GROQ_API_KEY = settings.GROQ_API_KEY
OPENAI_API_KEY = settings.OPENAI_API_KEY

con_err = ( ConnectionFailure, CursorNotFound, ServerSelectionTimeoutError, ConfigurationError )
tim_err = ( ExecutionTimeout, WTimeoutError, NetworkTimeout, WriteError, WriteConcernError, DocumentTooLarge )
key_and_name = ( KeyError, NameError, InvalidOperation )
 

def home(request,message):
    try:
        if 'name' in request.session:
            cli = MongoClient(MONGO_URI)
            uid = request.session['user_id']
            data = cli['users']['login'].find_one({'_id':ObjectId(uid[1:])})
            trimed_list=[]
            sizes = []
            for i in data['files_name']:
                #print(data)
                if i[-3:]=='pdf':
                    #print()
                    sizes.append(data[i[:-4]]['pdf'])
                elif i[-3:]=='doc':
                    sizes.append(data[i[:-4]]['doc'])
                else:
                    sizes.append(data[i[:-5]]['docx'])

                if '/' in i:
                    trimed_list.append( i.split("/")[1] )
                else:
                    trimed_list.append( i.split('\\')[1] )
            d={}
            # print(trimed_list)
            # print("----------------------------------")

            for i,j,siz in zip(data['files_name'], trimed_list, sizes):
                d[i]=[j,siz]
            
            
            # print(d)
            data_to_pass = {
                    'name': request.session['name'],
                    #'files' : data['files_name'],
                    'allowed_upload': 5-len(data['files_name']),
                    #'trimed_list': trimed_list
                    'table':d,
                    'message':message if message!="1" else '',
                    'sizes':sizes
                } 
            return render(request,'home.html',data_to_pass) 
        else:
            return redirect('login_page')
    except key_and_name as e:
        logout(request)
        request.session.flush()
        return render(request,'login.html',{'message':'login first..'})
    except con_err as e:
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        return render(request,'login.html',{'message':'Unable to connect to DB!'})
    except tim_err as e:
        data_to_pass={'message': str(e) }
        return render( request,'home.html',data_to_pass )
    except:
        logout(request)
        request.session.flush()
        return render(request,'login.html',{'message':'login first..'})

def login_page(request):
    return render(request,'login.html')

def login_check(request):
    try:
        if request.method == "POST":
            email = request.POST['email']
            pwd = request.POST['password']
            globals()['client'] = MongoClient(MONGO_URI)
            data = globals()['client']['users']['login'].find_one({'email':email,'password':pwd})
            #print(data)
            if data:
                request.session['name'] = data['name']
                request.session['user_id'] = "_"+str(data['_id'])
                url = reverse('home', kwargs={'message':'1'})
                return redirect(url)
                return render(request,'home.html',data_to_pass) 
            else:
                return render(request,'login.html',{'message':'Invalid credentials!'})
        else:
            return render(request,'login.html')
    
    except key_and_name as e:
        logout(request)
        request.session.flush()
        return render(request,'login.html',{'message':'login first..'})
    except con_err as e:
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        return render(request,'login.html',{'message':'Unable to connect to DB!'})
    except tim_err as e:
        url = reverse('home', kwargs={'message':str(e)})
        return redirect(url)
        data_to_pass={'message': str(e) }
        return render( request,'home.html',data_to_pass )
    
def register(request):
    return render(request,'register.html')

def register_new_user(request):
    try:
        if request.method == "POST":
            name = request.POST['name']
            email = request.POST['email']
            username = request.POST['username']
            password = request.POST['password']
            globals()['client'] = MongoClient(MONGO_URI)
            if not client['users']['login'].find_one({'email':email}):
                result=client['users']['login'].insert_one({
                        'name':name,
                        'email':email,
                        'username':username,
                        'password':password,
                        'files_name':[]
                    })
                db = client['pdf_embd']
                db.create_collection("_"+str(result.inserted_id))
                return redirect('login_page')
            else:
                return render(request,'register.html',{'message':'Email already exists...!'})
        
    except con_err as e:
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        return render(request,'login.html',{'message':'Unable to connect to DB!'})
    except tim_err as e:
        url = reverse('home', kwargs={'message':str(e)})
        return redirect(url)
        data_to_pass={ 'name': request.session['name'], 'message': str(e) }
        return render( request,'home.html',data_to_pass )
    except key_and_name as e:
        logout(request)
        request.session.flush()
        return render(request,'login.html',{'message':'login first..'})
    
def logout_user(request):
    try:
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        
        return redirect('login_page')
    except key_and_name as e:
        logout(request)
        request.session.flush()
        return render(request,'login.html',{'message':'login first..'})
    except:
        return redirect('login_page')
    

def file_upload(request):
    # try:
        # load_dotenv()
        # llm = ChatGroq(groq_api_key = os.getenv('GROQ_API_KEY'), model_name="Llama3-70b-8192")
        load_dotenv()
        if (request.method == "POST") and ('name' in request.session) and ('user_id' in request.session):
            file = request.FILES['document']
            file_name = file.name.replace(" ","_")
            if file_name.count(".")!=1:
                url = reverse('home', kwargs={'message':"Upload file with no '.' in its name"})
                return redirect(url)

            if file_name[-3:].lower() == 'pdf':
                file_type = 'pdf'
            elif file_name[-3:].lower() == 'doc':
                file_type = 'doc'
            else:
                file_type = 'docx'
            docmt=MongoClient(os.getenv("MONGO_DB_VECTOR_URI"))['users']['login'].find_one({'_id':ObjectId(request.session['user_id'][1:])})
            file_list = docmt['files_name']
            # print(docmt)
            # for i in file_list:
            #     print(i,">>>>>>>>>>>>>.")
            #     print()
            if request.session['user_id']+"\\"+file_name in file_list:
                url = reverse('home', kwargs={'message':'File already exists...!'})
                return redirect(url)

            path_to_save = request.session['user_id']  
            os.mkdir( os.path.join(settings.BASE_DIR,'app',request.session['user_id']) )
            absolute_file_path = os.path.join(settings.BASE_DIR,'app',request.session['user_id'],file_name)
            relative_file_path = os.path.join(request.session['user_id'],file_name)

            with open(absolute_file_path, 'wb+') as destination_file:
                for chunk in file.chunks():
                    destination_file.write(chunk)
            mong_cli = MongoClient(os.getenv("MONGO_DB_VECTOR_URI"))
            vec_collection = mong_cli['pdf_embd'][request.session['user_id']]
            
            if file_type == 'pdf':
                #print("YES PDF",absolute_file_path)
                #print(os.path.join(request.session['user_id'],file_name))
                loader = PyPDFLoader( absolute_file_path )  # Data Ingestion
                docs = loader.load()  # Document Loading
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)  # Chunk Creation
                final_documents = text_splitter.split_documents(docs)
                #print(final_documents)
                #print(os.getenv("MONGO_DB_VECTOR_URI"))
                # Create the vector store
                vector_search = MongoDBAtlasVectorSearch.from_documents(
                    documents = final_documents,
                    embedding = OpenAIEmbeddings(disallowed_special=(),model="text-embedding-3-small",api_key=OPENAI_API_KEY),
                    collection = vec_collection,
                    index_name = "vector_index"
                )
            else:
                loader = UnstructuredWordDocumentLoader(absolute_file_path)  # Data Ingestion
                docs = loader.load()  # Document Loading
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)  # Chunk Creation
                final_documents = text_splitter.split_documents(docs)
                # Create the vector store
                vector_search = MongoDBAtlasVectorSearch.from_documents(
                    documents = final_documents,
                    embedding = OpenAIEmbeddings(disallowed_special=(),model="text-embedding-3-small",api_key=OPENAI_API_KEY),
                    collection = vec_collection,
                    index_name = "vector_index"
                )
            if os.path.exists(os.path.join(settings.BASE_DIR,'app',request.session['user_id'],file_name)):
                shutil.rmtree(os.path.join(settings.BASE_DIR,'app',request.session['user_id']))
            mong_cli['users']['login'].find_one_and_update(
                { '_id': ObjectId( request.session['user_id'][1:] ) },
                {'$push': {'files_name':  str( os.path.join(request.session['user_id'],file_name) ) }}
            )
            mong_cli['users']['login'].find_one_and_update(
                {'_id': ObjectId( request.session['user_id'][1:] ) },
                {
                    '$set': { 
                                str( os.path.join(request.session['user_id'],file_name) ) : str(request.POST['file_size']) 
                    }
                }
            )
            mong_cli.close()
            url = reverse('home', kwargs={'message':'Uploaded..!'})
            return redirect(url)
            return redirect('home')
        else:
            return render(request,'login.html',{'message':'Login first..'})
        
'''    except con_err as e:
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        if os.path.exists(os.path.join(settings.BASE_DIR,'app',request.session['user_id'],file_name)):
            shutil.rmtree(os.path.join(settings.BASE_DIR,'app',request.session['user_id']))
        return render(request,'login.html',{'message':'Unable to connect to DB!'})
    except tim_err as e:
        if os.path.exists(os.path.join(settings.BASE_DIR,'app',request.session['user_id'],file_name)):
            shutil.rmtree(os.path.join(settings.BASE_DIR,'app',request.session['user_id']))
        url = reverse('home', kwargs={'message':str(e)})
        return redirect(url)
        data_to_pass={ 'name': request.session['name'], 'message': str(e) }
        return render( request,'home.html',data_to_pass )
    except key_and_name as e:
        if os.path.exists(os.path.join(settings.BASE_DIR,'app',request.session['user_id'],file_name)):
            shutil.rmtree(os.path.join(settings.BASE_DIR,'app',request.session['user_id']))
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        return render(request,'login.html',{'message':'login first..'})
    
    except Exception as e:
        if os.path.exists(os.path.join(settings.BASE_DIR,'app',request.session['user_id'],file_name)):
            shutil.rmtree(os.path.join(settings.BASE_DIR,'app',request.session['user_id']))
        logout(request)
        request.session.flush()
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        return render(request,'login.html',{'message':'Error...'+str(e)})
'''    
def delete_document(request):
    if request.method=="POST" and 'name' in request.session:
        
        try:
            doc_id = request.POST['doc_id']
            doc_path = os.path.join(settings.BASE_DIR,'app',doc_id)
            #print(doc_id)
            #print(doc_path)
            cli = MongoClient(MONGO_URI)
            cli['pdf_embd'][request.session['user_id']].delete_many(
                {'source': doc_path }
            )
            if doc_id[-3:]=='pdf':
                unset_key=doc_id[:-4]
            elif doc_id[-3:]=='doc':
                unset_key=doc_id[:-4]
            else:
                unset_key=doc_id[:-5]
            cli['users']['login'].update_one(
                {"_id": ObjectId( request.session['user_id'][1:] ) },
                {
                    "$pull": {
                        "files_name": doc_id
                    },
                    "$unset": {
                       unset_key : "" 
                    }
                }
            )
            cli.close()
            url = reverse('home', kwargs={'message':'Deleted successfully...'})
            return redirect(url)
            return redirect('home.html')
        except Exception as e:
            url = reverse('home', kwargs={'message':str(e)})
            return redirect(url)
            return redirect('home.html')
    else:
        if 'client' in globals():
            cli = globals()['client']
            cli.close()
        logout(request)
        request.session.flush()
        return render(request,'login.html',{'message':'Login first..!'})

@api_view(['POST'])
def prompt(request):
    try:
        load_dotenv()
        if 'name' in request.session:
            jsonData = json.loads(request.body)
            prompt_text = jsonData.get('text')
            print(prompt_text)
            print(os.getenv("MONGO_DB_VECTOR_URI"))
            vectorstore = MongoDBAtlasVectorSearch.from_connection_string(
                os.getenv("MONGO_DB_VECTOR_URI"),
                f"pdf_embd.{request.session['user_id']}",
                OpenAIEmbeddings(disallowed_special=()),
                index_name="vector_index",
            )
            llm = ChatGroq(groq_api_key = os.getenv('GROQ_API_KEY'), model_name="Llama3-70b-8192")
            prompt = ChatPromptTemplate.from_template(
                        """
                        Answer the questions based on the provided context only.
                        Please provide the most accurate response based on the question.
                        <context>
                        {context}
                        <context>
                        Questions:{input}
                        """
                    )
            document_chain = create_stuff_documents_chain(llm, prompt)
            retriever = vectorstore.as_retriever(
                        search_type = "similarity",
                        search_kwargs = {"k": 10, "score_threshold": 0.75},
                        
                    )
            # print(retriever.__dict__)
            retrieval_chain = create_retrieval_chain(retriever, document_chain)
            response = retrieval_chain.invoke({'input':prompt_text })
            print(response['answer'])   
            return Response({'reply':response['answer']})
    except:
        return Response({'reply':"Error"})