Library=[]
def add_books():
    i=0
    no=int(input("Enter the No of Books to be added: "))
    for i in range(no):
        Book_name=input("Enter the book name: ")
        Book_id=int(input("Enter the book id: "))
        Aurthor=input("Enter the Aurthor name: ")
        Year=int(input("Enter the Year:"))
        Books={"Book_name":Book_name,"Book_id":Book_id,"Aurthor":Aurthor,"Year":Year} 
        Library.append(Books)
        print("\nBooks added successfully")
        print("  ")
    print("-----------------------------------------------------------")

def Display():
    Total=len(Library)
    i=0
    if(Total==0):
        print("The Library is empty")
    
    else:
        for i in range(Total):
            print(Library[i])
    print("-----------------------------------------------------------")       
  

def search():
    id=int(input("Enter the book id to search: "))
    found=False
    for Books in Library:
        if(Books["Book_id"]==id):
            print(Books)
           
            found=True
    if(found==True):
        print("Book searched successfully")
    else:
        print("Book not found")
    print("-----------------------------------------------------------")
def main():
    while 1:
        print("\n1.Add book ")
        print("\n2.display")
        print("\n3.search")
        print("\n4.Exit")
        print("------------------------------------------------------- ")
        ch=int(input("Enter the chooice: "))
    
    
        if(ch==1):
            add_books()
        elif(ch==2):
            Display()
        elif(ch==3):
            search()
        elif ch==4:
            print("program excuted successfully")
            break
        else:
            print("Invalid chooice")
main()